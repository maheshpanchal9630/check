# =====================================================
# blockchain.py
# COMPLETE UPDATED VERSION
# =====================================================

import hashlib
import json

# =====================================================
# CREATE HASH
# =====================================================

def compute_hash(data, prev_hash):

    block_string = json.dumps({

        "data": data,
        "prev_hash": prev_hash

    }, sort_keys=True).encode()

    return hashlib.sha256(
        block_string
    ).hexdigest()

# =====================================================
# VERIFY BLOCKCHAIN
# =====================================================

def verify_chain(records):

    # =====================================================
    # EMPTY CHAIN
    # =====================================================

    if len(records) == 0:

        return {

            "valid": False,

            "message":
            "No blockchain records found"

        }

    # =====================================================
    # SAFE SORT
    # =====================================================

    records = sorted(

        records,

        key=lambda x:
        x.get("block_number", 0)

    )

    # =====================================================
    # VERIFY CHAIN
    # =====================================================

    for i in range(len(records)):

        block = records[i]

        # =====================================================
        # GENESIS BLOCK
        # =====================================================

        if i == 0:

            if block.get("prev_hash") != "0" * 64:

                return {

                    "valid": False,

                    "tampered_at": i + 1,

                    "message":
                    "Genesis block invalid ❌"

                }

            continue

        previous_block = records[i - 1]

        # =====================================================
        # HASH CHECK
        # =====================================================

        if block.get("prev_hash") != previous_block.get("hash"):

            return {

                "valid": False,

                "tampered_at": i + 1,

                "message":
                f"Block {i+1} tampered ❌"

            }

        # =====================================================
        # RECREATE HASH
        # =====================================================

        data = {

            "product":
            block.get("product"),

            "location":
            block.get("location"),

            "date":
            block.get("date"),

            "time":
            block.get("time"),

            "details":
            block.get("details"),

            "updated_by":
            block.get("updated_by"),

            "role":
            block.get("role"),

            "block_number":
            block.get("block_number")

        }

        recalculated_hash = compute_hash(

            data,

            block.get("prev_hash")

        )

        # =====================================================
        # DATA TAMPER CHECK
        # =====================================================

        if recalculated_hash != block.get("hash"):

            return {

                "valid": False,

                "tampered_at": i + 1,

                "message":
                f"Block {i+1} data modified ❌"

            }

    # =====================================================
    # SUCCESS
    # =====================================================

    return {

        "valid": True,

        "message":
        "Blockchain verified successfully ✅"

    }
