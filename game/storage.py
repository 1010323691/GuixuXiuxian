"""SQLite is the only authoritative state; all successful writes are atomic."""
import json
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from . import config as C
from . import rules
from . import growth
from . import cadence


def encode(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


class Store:
    def __init__(self,data_dir,migrate=False,clock=None):
        self.clock=clock if clock is not None else time.time
        folder=Path(data_dir)
        folder.mkdir(parents=True,exist_ok=True)
        self.path=folder/'game.db'
        self.migration_backup=None
        existed=self.path.exists()
        if existed and self.path.stat().st_size==0:
            raise ValueError('存档数据库为空，拒绝覆盖；请保留原件并恢复备份。')
        db=self.connect()
        try:
            if existed:
                if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise ValueError('存档数据库完整性检查失败')
                if {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} != {'current','requests'}:
                    raise ValueError('存档表结构不受支持')
                version=db.execute('SELECT schema_version FROM current WHERE id=1').fetchone()
                if version and version[0]==1 and C.SCHEMA_VERSION==2:
                    if not migrate:
                        raise ValueError('这是第1版存档。请先停止旧服务，再使用 --migrate-save 显式备份并迁移；原件未更改。')
                    self._migrate_v1(db)
                self._read(db)
                self._upgrade_content(db)
            else:
                db.executescript('CREATE TABLE current (id INTEGER PRIMARY KEY CHECK(id=1), schema_version INTEGER NOT NULL, revision INTEGER NOT NULL, state TEXT NOT NULL, slot TEXT NOT NULL); CREATE TABLE requests (request_id TEXT PRIMARY KEY,payload TEXT NOT NULL);')
                db.execute('INSERT INTO current VALUES(1,?,0,?,?)',(C.SCHEMA_VERSION,'null','null'))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        self.snapshot()

    def _migrate_v1(self,db):
        """Back up a locked, verified v1 database before any migration writes."""
        from . import world
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT schema_version,revision,state,slot FROM current WHERE id=1').fetchone()
        # Another startup may have finished migration while we waited for the lock.
        if row and row[0]==C.SCHEMA_VERSION:
            return
        if not row or row[0]!=1 or not rules.valid_int(row[1],0,2**63-1):
            raise ValueError('旧存档版本或元信息无效，拒绝迁移')
        if db.execute('SELECT count(*) FROM current').fetchone()[0]!=1:
            raise ValueError('旧存档当前进度记录数量无效')
        state,slot=json.loads(row[2]),json.loads(row[3])
        rules.validate_legacy_state(state)
        rules.validate_legacy_state(slot)
        ledger=db.execute('SELECT request_id,payload FROM requests ORDER BY request_id').fetchall()
        if any(not isinstance(key,str) or not isinstance(value,str) for key,value in ledger):
            raise ValueError('旧存档请求账本无效')

        self._backup_locked(db,'game.schema1.')

        def upgrade(old):
            if old is None:
                return None
            original=json.loads(encode(old))
            upgraded=world.migrate_v1(old)
            if not isinstance(upgraded,dict) or set(upgraded)!=set(original)|{'world'} or any(upgraded[key]!=value for key,value in original.items()):
                raise ValueError('迁移改变了原有角色字段，拒绝提交')
            rules.validate_state(upgraded)
            return upgraded

        upgraded_state,upgraded_slot=upgrade(state),upgrade(slot)
        db.execute('UPDATE current SET schema_version=?,state=?,slot=? WHERE id=1',
                   (C.SCHEMA_VERSION,encode(upgraded_state),encode(upgraded_slot)))
        self._read(db)
        # The outer constructor commits schema/state/slot together; revision/ledger untouched.

    def _backup_locked(self,db,prefix):
        """Verify a consistent original while the caller holds BEGIN IMMEDIATE."""
        row=db.execute('SELECT schema_version,revision,state,slot FROM current WHERE id=1').fetchone()
        ledger=db.execute('SELECT request_id,payload FROM requests ORDER BY request_id').fetchall()
        descriptor,backup_name=tempfile.mkstemp(prefix=prefix,suffix='.bak.db',dir=self.path.parent)
        os.close(descriptor)
        backup=Path(backup_name)
        try:
            source=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
            target=sqlite3.connect(backup)
            try:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise ValueError('迁移备份完整性检查失败')
                if target.execute('SELECT schema_version,revision,state,slot FROM current WHERE id=1').fetchone()!=row or target.execute('SELECT request_id,payload FROM requests ORDER BY request_id').fetchall()!=ledger:
                    raise ValueError('迁移备份与原件内容不一致')
            finally:
                target.close();source.close()
            with backup.open('r+b') as stream:os.fsync(stream.fileno())  # Windows rejects fsync on read-only handles
            self.migration_backup=backup
        except Exception:
            backup.unlink(missing_ok=True)
            raise

    @staticmethod
    def _needs_content_upgrade(state):
        return growth.is_longline(state) and (growth.curve_version(state)!=2 or any(key not in state['world']['r3'] for key in ('cadence','journey')))

    def _upgrade_content(self,db):
        revision,state,slot=self._read(db)
        if not any(self._needs_content_upgrade(s) for s in (state,slot)):return
        if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
        # Re-read after obtaining the lock: a competing startup may have upgraded.
        revision,state,slot=self._read(db)
        if not any(self._needs_content_upgrade(s) for s in (state,slot)):return
        self._backup_locked(db,'game.r3-before-r4.')
        now=self._now()
        from . import journey
        def upgrade(old):
            if not self._needs_content_upgrade(old):return old
            result=growth.upgrade_legacy(old,now)
            result=cadence.migrate_legacy(result,now)
            journey.migrate(result['world'])
            rules.validate_state(result)
            growth.validate(result,check_balance=True)
            cadence.validate(result,check_clock=True)
            return result
        state,slot=upgrade(state),upgrade(slot)
        if revision==2**63-1:raise ValueError('存档版本号已到上限，拒绝覆盖')
        db.execute('UPDATE current SET revision=?,state=?,slot=? WHERE id=1',(revision+1,encode(state),encode(slot)))
        self._read(db)

    def connect(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            db.execute('PRAGMA busy_timeout=5000')
            db.execute('PRAGMA synchronous=FULL')
        except Exception:
            db.close();raise  # e.g. corrupt file: release the handle so the original is not left locked
        return db

    def _read(self,db):
        row=db.execute('SELECT schema_version,revision,state,slot FROM current WHERE id=1').fetchone()
        if not row or row[0]!=C.SCHEMA_VERSION or not rules.valid_int(row[1],0,2**63-1):
            raise ValueError('存档版本或元信息不受支持')
        state,slot=json.loads(row[2]),json.loads(row[3])
        rules.validate_state(state);rules.validate_state(slot)
        growth.validate(state,check_balance=True);growth.validate(slot,check_balance=True)
        cadence.validate(state,check_clock=True);cadence.validate(slot,check_clock=True)
        return row[1],state,slot

    def _now(self):
        value=self.clock()
        if type(value) not in (int,float) or value<0:
            raise ValueError('服务端时钟无效')
        try:return int(value)
        except (ValueError,OverflowError):raise ValueError('服务端时钟无效') from None

    @staticmethod
    def _context(state,now):
        raw_now=now
        if growth.is_longline(state):
            account=state['world']['r3'].get('growth') or {}
            now=max(now,account.get('last_settled') or now)
        return {'now':now,'day':datetime.fromtimestamp(now,timezone.utc).date().isoformat(),'raw_now':raw_now}

    def _snapshot(self,revision,state,slot,events=None,duplicate=False,battle_report=None):
        summary=None if slot is None else '%s · %s · 第%d行'%(slot['name'],C.REALMS[slot['realm']],slot['actions_taken'])
        now=self._now()
        projected,growth_view=growth.preview(state,now)
        projected=cadence.sync(projected,self._context(projected,now)['now'])
        view=rules.project(projected,context=self._context(projected,now))
        longline=growth.is_longline(state)
        view['profile']={'mode':'longline' if longline else 'free','load_policy':'仅恢复安全位置，保留当前剧情战斗、成长与全部资产经济及奖励资格；未入世序章仍完整恢复。' if longline else '完整恢复手动检查点。'}
        if growth_view is not None:view['growth']=growth_view
        result=dict(ok=True,duplicate=duplicate,revision=revision,state=state,view=view,save={'exists':slot is not None,'summary':summary},events=events or [])
        # 自动斗法回放仅随本次响应返回，不入存档；重复请求/刷新后只留日志。
        if battle_report is not None:result['battle_report']=battle_report
        return result

    def snapshot(self):
        db=self.connect()
        try:return self._snapshot(*self._read(db))
        finally:db.close()

    def write(self,endpoint,payload):
        request_id=payload.get('request_id')
        revision=payload.get('expected_revision')
        if not isinstance(request_id,str) or not 1<=len(request_id)<=128 or any(not 32<=ord(c)<=126 for c in request_id):
            raise rules.GameError('BAD_REQUEST','请求编号须为1至128个可打印ASCII字符。',400)
        if not rules.valid_int(revision,0,2**63-1):
            raise rules.GameError('BAD_REQUEST','进度版本须为非负整数。',400)
        extra={'name'} if endpoint=='new-game' else {'action','params'} if endpoint=='action' else set()
        fields=set(payload)
        if endpoint=='new-game':fields.discard('mode')
        if fields != {'request_id','expected_revision'}|extra:
            raise rules.GameError('BAD_REQUEST','请求字段不完整或包含未知字段。',400)
        canonical=encode({'endpoint':endpoint,'payload':payload})
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT payload FROM requests WHERE request_id=?',(request_id,)).fetchone()
            current,state,slot=self._read(db)
            if old:
                if old[0]!=canonical:raise rules.GameError('REQUEST_ID_REUSED','请求编号已用于其他操作。',409)
                result=self._snapshot(current,state,slot,duplicate=True)
                db.commit();return result
            if revision!=current:
                exc=rules.GameError('STALE_STATE','进度已在其他页面更新，请刷新后重试。',409)
                exc.revision=current;raise exc
            events=[]
            now=self._now()
            state=growth.sync(state,now)
            state=cadence.sync(state,self._context(state,now)['now'])
            context=self._context(state,now)
            if endpoint=='new-game':
                mode=payload.get('mode','longline')
                if not isinstance(mode,str) or mode not in {'free','longline'}:
                    raise rules.GameError('BAD_REQUEST','游戏模式须为free或longline。',400)
                state=cadence.sync(growth.sync(rules.new_game(payload['name'],mode=mode),now),now);slot=None;events=['初入青岚村，修行自此开始。']
            elif endpoint=='action':
                before=state
                state,events=rules.apply_action(state,payload['action'],payload['params'],context=context)
                state=growth.finish(before,state,now)
                state=cadence.sync(state,self._context(state,now)['now'])
            elif endpoint=='save':
                if state is None:raise rules.GameError('NO_GAME','请先创建角色。')
                slot=json.loads(encode(state));events=['已将当前进度保存为手动检查点。']
            elif endpoint=='load':
                if slot is None:raise rules.GameError('NO_SAVE','尚无手动检查点，请先存档。')
                state,events=growth.load_checkpoint(state,slot)
            else:raise rules.GameError('BAD_REQUEST','未知存档操作。',400)
            rules.validate_state(state);rules.validate_state(slot)
            growth.validate(state,check_balance=True);growth.validate(slot,check_balance=True)
            cadence.validate(state,check_clock=True);cadence.validate(slot,check_clock=True)
            current+=1
            db.execute('UPDATE current SET revision=?,state=?,slot=? WHERE id=1',(current,encode(state),encode(slot)))
            db.execute('INSERT INTO requests VALUES(?,?)',(request_id,canonical))
            result=self._snapshot(current,state,slot,events,battle_report=context.get('battle_report') if endpoint=='action' else None)
            db.commit()
            return result
        except Exception:
            db.rollback();raise
        finally:db.close()
