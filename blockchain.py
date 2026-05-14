# =====================================================
# blockchain.py
# =====================================================

import hashlib
import json

# =====================================================
# HASH COMPUTE
# =====================================================

def compute_hash(data: dict, prev_hash: str) -> str:

    block_string = json.dumps(
        data,
        sort_keys=True,
        default=str
    ) + prev_hash

    return hashlib.sha256(
        block_string.encode()
    ).hexdigest()

# =====================================================
# VERIFY CHAIN
# =====================================================

def verify_chain(trace_records: list) -> dict:

    if not trace_records:

        return {
            "valid": False,
            "tampered_at": None,
            "message": "No records found"
        }

    # =====================================================
    # SORT BLOCKS
    # =====================================================

    trace_records = sorted(
        trace_records,
        key=lambda x: x.get("block_number", 0)
    )

    # =====================================================
    # CHECK MISSING BLOCKS
    # =====================================================

    expected = 1

    for rec in trace_records:

        if rec.get("block_number") != expected:

            return {
                "valid": False,
                "tampered_at": expected,
                "message": f"Block {expected} missing or deleted ❌"
            }

        expected += 1

    # =====================================================
    # VERIFY HASHES
    # =====================================================

    for i, record in enumerate(trace_records):

        if i == 0:
            expected_prev = "0" * 64
        else:
            expected_prev = trace_records[i - 1]["hash"]

        data_for_hash = {

            k: v for k, v in record.items()

            if k not in [
                "hash",
                "prev_hash",
                "_id"
            ]
        }

        recalculated = compute_hash(
            data_for_hash,
            expected_prev
        )

        stored_hash = record.get("hash")

        if recalculated != stored_hash:

            return {
                "valid": False,
                "tampered_at": i + 1,
                "message": f"Block {i + 1} tampered ❌"
            }

    return {
        "valid": True,
        "tampered_at": None,
        "message": f"Blockchain verified — {len(trace_records)} blocks secure ✅"
    }
