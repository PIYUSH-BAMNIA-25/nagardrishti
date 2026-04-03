"""
supabase_client.py — Supabase Integration for Complaint Storage

Manages the connection to a Supabase PostgreSQL database and provides
helper methods for storing, retrieving, and updating civic complaints.

Expected table schema (create in Supabase dashboard):

    CREATE TABLE complaints (
        id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        created_at  TIMESTAMPTZ DEFAULT now(),
        category    TEXT NOT NULL,
        description TEXT,
        severity    INT,
        latitude    FLOAT,
        longitude   FLOAT,
        location    TEXT,
        status      TEXT DEFAULT 'Pending',    -- Pending | In Progress | Resolved
        image_url   TEXT,
        pdf_url     TEXT,
        email_sent  BOOLEAN DEFAULT FALSE
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

        Parameters
        ----------
        data : dict
            Must include at least: category, description.
            Optional: severity, latitude, longitude, location,
            image_url, pdf_url, email_sent.

        Returns
        -------
        dict — the inserted row
        """
        response = self.client.table(TABLE_NAME).insert(data).execute()
        logger.info("Complaint inserted: %s", response.data)
        return response.data[0] if response.data else {}

    # ── Read ──────────────────────────────────────────────────

    def get_all_complaints(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all complaints, optionally filtered by status.

        Parameters
        ----------
        status : str, optional — "Pending", "In Progress", or "Resolved"
        """
        query = self.client.table(TABLE_NAME).select("*")
        if status:
            query = query.eq("status", status)
        response = query.order("created_at", desc=True).execute()
        return response.data or []

    def get_complaint_by_id(self, complaint_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single complaint by UUID."""
        response = (
            self.client.table(TABLE_NAME)
            .select("*")
            .eq("id", complaint_id)
            .single()
            .execute()
        )
        return response.data

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
