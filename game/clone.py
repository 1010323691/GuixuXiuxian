"""Fast deep copy for plain game state (dict/list/str/int/float/bool/None).

pickle round-trip produces an independent structure equal to copy.deepcopy (shared
references are preserved the same way) at a fraction of the cost.
"""
import pickle


def clone(value):
    return pickle.loads(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
