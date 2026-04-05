"""
supabase_client.py — Supabase Integration for Complaint Storage

Manages the connection to a Supabase PostgreSQL database and provides
helper methods for storing, retrieving, and updating civic complaints.

Expected table schema (create in Supabase dashboard):

    CREATE TABLE complaints (
        id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        created_at      TIMESTAMPTZ DEFAULT now(),
        complaint_id    TEXT UNIQUE NOT NULL,
        category        TEXT NOT NULL,
        description     TEXT,
        severity        INT,
        severity_label  TEXT,
        latitude        FLOAT,
        longitude       FLOAT,
        location        TEXT,
        status          TEXT DEFAULT 'Pending',
        is_verified     BOOLEAN DEFAULT FALSE,
        veracity_reason TEXT,
        image_url       TEXT,
        pdf_url         TEXT,
        email_sent      BOOLEAN DEFAULT FALSE,
        municipal_dept  TEXT,
        source          TEXT
    );
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

TABLE_NAME = "complaints"


class SupabaseClient:
    """Thin wrapper around the Supabase Python client for complaint CRUD."""

    def __init__(self) -> None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.warning("Supabase credentials not set — database operations will fail.")
        # TODO: Handle missing credentials gracefully in production
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # ── Create ────────────────────────────────────────────────

    def insert_complaint(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert a new complaint record.
        Only sends columns that exist in the Supabase schema.
        """
        ALLOWED_COLUMNS = {
            'complaint_id', 'category', 'description',
            'severity', 'severity_label', 'latitude', 'longitude',
            'location', 'status', 'is_verified', 'veracity_reason',
            'image_url', 'pdf_url', 'email_sent', 'municipal_dept', 'source'
        }
        try:
            # Only send columns that exist in Supabase schema
            clean_data = {
                k: v for k, v in data.items()
                if k in ALLOWED_COLUMNS and v is not None
            }
            response = self.client.table(TABLE_NAME).insert(clean_data).execute()
            logger.info("Complaint inserted: %s", response.data)
            return response.data[0] if response.data else {}
        except Exception as e:
            print(f"[Supabase] insert error: {e}")
            return None

    # ── Read ──────────────────────────────────────────────────

    def get_all_complaints(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all complaints, optionally filtered by status.
        """
        try:
            query = self.client.table(TABLE_NAME).select("*")
            if status:
                query = query.eq("status", status)
            response = query.order("created_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            print(f"[Supabase] get_all_complaints error: {e}")
            return []

    def get_complaint_by_id(self, complaint_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single complaint by UUID."""
        try:
            response = (
                self.client.table(TABLE_NAME)
                .select("*")
                .eq("id", complaint_id)
                .single()
                .execute()
            )
            return response.data
        except Exception as e:
            print(f"[Supabase] get_complaint_by_id error: {e}")
            return None

    def get_complaint_by_public_id(self, complaint_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single complaint by the public-facing complaint_id value."""
        try:
            response = (
                self.client.table(TABLE_NAME)
                .select("*")
                .eq("complaint_id", complaint_id)
                .single()
                .execute()
            )
            return response.data
        except Exception as e:
            print(f"[Supabase] get_complaint_by_public_id error: {e}")
            return None

    # ── Update ────────────────────────────────────────────────

    def update_status(self, complaint_id: str, new_status: str) -> Dict[str, Any]:
        """
        Update the status of an existing complaint.

        Parameters
        ----------
        complaint_id : str — UUID
        new_status : str — "Pending", "In Progress", or "Resolved"
        """
        response = (
            self.client.table(TABLE_NAME)
            .update({"status": new_status})
            .eq("id", complaint_id)
            .execute()
        )
        logger.info("Complaint %s → %s", complaint_id, new_status)
        return response.data[0] if response.data else {}

    # ── Geo Queries ───────────────────────────────────────────

    def get_complaints_with_coordinates(self) -> List[Dict[str, Any]]:
        """Fetch all complaints that have GPS coordinates (for the heatmap)."""
        response = (
            self.client.table(TABLE_NAME)
            .select("*")
            .not_.is_("latitude", "null")
            .not_.is_("longitude", "null")
            .execute()
        )
        return response.data or []
    # ── Storage ───────────────────────────────────────────────
    # IMPORTANT: The Supabase Storage bucket must be set to PUBLIC
    # in Supabase Dashboard → Storage → complaint-images → 
    # Policies → Enable public access
    # Otherwise get_public_url() returns URLs that require auth

    def upload_image(self, image_path: str, complaint_id: str) -> str:
        """
        Uploads image to Supabase Storage bucket.
        Returns public URL of uploaded image.
        Returns empty string if upload fails.
        
        Args:
            image_path  : local path to image file
            complaint_id: used to create unique storage filename
        """
        try:
            import os
            from config import SUPABASE_STORAGE_BUCKET
            
            if not image_path or not os.path.exists(image_path):
                print(f"[Storage] Image not found: {image_path}")
                return ""
            
            # Create unique filename for storage
            ext = os.path.splitext(image_path)[1] or ".jpg"
            storage_filename = f"complaints/{complaint_id}_evidence{ext}"
            
            # Read image bytes
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            
            # Upload to Supabase Storage
            response = self.client.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                path=storage_filename,
                file=image_bytes,
                file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
            
            # Get public URL
            public_url = self.client.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(storage_filename)
            
            print(f"[Storage] ✅ Image uploaded: {public_url}")
            return public_url
            
        except Exception as e:
            print(f"[Storage] ❌ Upload failed: {type(e).__name__}: {e}")
            return ""

    def upload_image_bytes(self, image_bytes: bytes, complaint_id: str, ext: str = ".jpg") -> str:
        """
        Uploads image from bytes (used by vision engine 
        which has base64 snapshots, not file paths).
        Returns public URL or empty string.
        """
        try:
            from config import SUPABASE_STORAGE_BUCKET
            
            storage_filename = f"complaints/{complaint_id}_snapshot{ext}"
            
            response = self.client.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                path=storage_filename,
                file=image_bytes,
                file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
            
            public_url = self.client.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(storage_filename)
            
            print(f"[Storage] ✅ Snapshot uploaded: {public_url}")
            return public_url
            
        except Exception as e:
            print(f"[Storage] ❌ Snapshot upload failed: {e}")
            return ""

