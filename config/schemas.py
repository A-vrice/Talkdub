"""
JSON Schema定義（Groq Structured Outputs対応）
Design原則: 6. 一貫性 - 構造のルールを統一
"""

JOB_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version", "job_id", "created_at", "source",
        "languages", "media", "pipeline_params", "speakers",
        "segments", "outputs", "status"
    ],
    "properties": {
        "schema_version": {"type": "string", "const": "0.1"},
        "job_id": {"type": "string", "minLength": 8},
        "created_at": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["QUEUED", "PROCESSING", "COMPLETED", "FAILED", "PAUSED", "EXPIRED"]
        },
        "current_phase": {"type": ["string", "null"]},
        
        "source": {
            "type": "object",
            "additionalProperties": False,
            "required": ["platform", "video_id", "url"],
            "properties": {
                "platform": {"type": "string", "const": "youtube"},
                "video_id": {"type": "string"},
                "url": {"type": "string"}
            }
        },
        
        "languages": {
            "type": "object",
            "additionalProperties": False,
            "required": ["src_lang", "tgt_lang"],
            "properties": {
                "src_lang": {"type": "string"},
                "tgt_lang": {"type": "string"}
            }
        },
        
        "media": {
            "type": "object",
            "additionalProperties": False,
            "required": ["duration_sec", "audio_format"],
            "properties": {
                "duration_sec": {"type": ["number", "null"]},
                "audio_format": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "sample_rate_hz": {"type": "integer"},
                        "channels": {"type": "integer"}
                    }
                }
            }
        },
        
        "pipeline_params": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "max_atempo", "max_overlap_sec", "max_overlap_ratio",
                "overlap_duck_db", "hallucination_policy", "timeline_reference"
            ],
            "properties": {
                "max_atempo": {"type": "number"},
                "max_overlap_sec": {"type": "number"},
                "max_overlap_ratio": {"type": "number"},
                "overlap_duck_db": {"type": "number"},
                "hallucination_policy": {"type": "string"},
                "timeline_reference": {"type": "string"}
            }
        },
        
        "speakers": {"type": "array"},
        "segments": {"type": "array"},
        "outputs": {
            "type": "object",
            "additionalProperties": False,
            "required": ["dub_wav", "manifest_json", "segments_json"],
            "properties": {
                "dub_wav": {"type": ["string", "null"]},
                "manifest_json": {"type": ["string", "null"]},
                "segments_json": {"type": ["string", "null"]}
            }
        },
        
        "error": {"type": ["string", "null"]},
        "progress": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "completed_segments": {"type": "integer"},
                "total_segments": {"type": "integer"},
                "percent": {"type": "number"}
            }
        },
        
        "user_email": {"type": "string"},
        "download_count": {"type": "integer"},
        "expires_at": {"type": ["string", "null"]}
    }
}

TRANSLATION_PATCH_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "job_id", "src_lang", "tgt_lang", "patch"],
    "properties": {
        "schema_version": {"type": "string", "const": "0.1"},
        "job_id": {"type": "string"},
        "src_lang": {"type": "string"},
        "tgt_lang": {"type": "string"},
        "patch": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["seg_id", "tgt_text"],
                "properties": {
                    "seg_id": {"type": "string"},
                    "tgt_text": {"type": "string"}
                }
            }
        }
    }
}
