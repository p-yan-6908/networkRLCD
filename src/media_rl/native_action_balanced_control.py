"""Separate train-only three-repetition arm/transition-balanced seed schedule."""

from .native_action_excitation_control import BEHAVIORS, CAPS
from .native_protocol import finite, require

ABI = "native_three_arm_balanced_hold_control_v1"
EPOCH_STEPS = 32
PERMUTATIONS = ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0))
MAX_BLOCK_SEED = (0xFFFFFFFF - 2) // 3


def encoded_seed(block_seed, repetition):
    require(
        type(block_seed) is int
        and 0 <= block_seed <= MAX_BLOCK_SEED
        and type(repetition) is int
        and repetition in (0, 1, 2),
        "bounded block seed/exact three repetitions required",
    )
    return block_seed * 3 + repetition


def _mix(seed, counter):
    x = (seed ^ (((counter + 1) * 0x9E3779B9) & 0xFFFFFFFF)) & 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x7FEB352D) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 0x846CA68B) & 0xFFFFFFFF
    x ^= x >> 16
    return x


def assignment(behavior, epoch, seed):
    require(
        behavior in BEHAVIORS
        and type(epoch) is int
        and 0 <= epoch <= 512
        and type(seed) is int
        and 0 <= seed <= encoded_seed(MAX_BLOCK_SEED, 2),
        "bounded balanced training hold/epoch/encoded seed required",
    )
    if behavior == "fixed450":
        return 450000
    block_seed, repetition = divmod(seed, 3)
    initial = PERMUTATIONS[_mix(block_seed, 0) % 6]
    offset = 0
    if epoch:
        block, position = divmod(epoch - 1, 3)
        shifts = PERMUTATIONS[_mix(block_seed, block + 1) % 6]
        offset = sum(shifts[: position + 1]) % 3
    return CAPS[initial[(repetition + offset) % 3]]


def settled_cap(behavior, step, seed, features):
    require(
        type(step) is int
        and 0 <= step <= EPOCH_STEPS * 512
        and len(features) == 16
        and all(finite(v) and v >= 0 for v in features)
        and features[9] in (0, 1),
        "bounded causal 32-step balanced hold required",
    )
    return assignment(behavior, step // EPOCH_STEPS, seed)
