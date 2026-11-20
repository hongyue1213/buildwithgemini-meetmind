#!/usr/bin/env python3
"""Seed script for MeetMind Firestore collections.

Hardcodes the GCP project ID to avoid Agent Platform project number resolution issues.
"""
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-8581f7539bcb"

SAMPLE_MEETINGS = [
    {
        "id": "meet-20261118-ai-roadmap",
        "title": "Q4 AI Feature Roadmap & Architecture Review",
        "date": "2026-11-18",
        "attendees": ["Alice (PM)", "Bob (Tech Lead)", "Charlie (Frontend)", "Diana (Data)"],
        "topics": ["Gemini 3.8 Flash Integration", "Meeting Transcription", "Vector Indexing"],
        "summary": "Discussed the integration of Gemini 3.8 Flash for audio transcription and meeting indexing. Decided to adopt Firestore for meeting records and Vertex AI for vector embeddings.",
        "key_takeaways": [
            "Adopted Gemini 3.8 Flash as the primary reasoning and parsing model.",
            "Firestore chosen for structured meeting metadata and action items.",
            "Targeting MVP demo by end of November 2026."
        ],
        "action_items": [
            {"task": "Set up Firestore collections and schemas", "owner": "Bob", "deadline": "2026-11-22", "status": "In Progress", "priority": "High"},
            {"task": "Draft UI card prototypes for meeting summary", "owner": "Charlie", "deadline": "2026-11-25", "status": "Pending", "priority": "Medium"}
        ]
    },
    {
        "id": "meet-20261119-budget-sync",
        "title": "Engineering Cloud Budget & Resource Planning",
        "date": "2026-11-19",
        "attendees": ["Alice (PM)", "Bob (Tech Lead)", "Elena (Finance)"],
        "topics": ["Cloud Run Quotas", "Agent Runtime Costs", "Storage Lifecycle"],
        "summary": "Reviewed Google Cloud resource consumption and pricing estimates for Agent Runtime and Cloud Storage. Confirmed budget approval for the AI knowledge base pilot.",
        "key_takeaways": [
            "Approved $2,500/month pilot budget for Vertex AI and Cloud Run.",
            "Agreed to implement 30-day lifecycle expiration for raw meeting audio in GCS."
        ],
        "action_items": [
            {"task": "Configure GCS lifecycle policy for meeting audio bucket", "owner": "Bob", "deadline": "2026-11-24", "status": "Pending", "priority": "Medium"},
            {"task": "Submit Q4 revised cloud forecast to finance", "owner": "Alice", "deadline": "2026-11-21", "status": "Completed", "priority": "High"}
        ]
    },
    {
        "id": "meet-20261120-client-feedback",
        "title": "Enterprise Pilot Feedback & Requirements Sync",
        "date": "2026-11-20",
        "attendees": ["Alice (PM)", "Frank (Customer Success)", "Grace (Sales)"],
        "topics": ["Transcript Accuracy", "Action Item Notifications", "Slack Integration"],
        "summary": "Synthesized feedback from 3 pilot customers. Accuracy of speaker attribution and action item export to Slack were voted the top requested features.",
        "key_takeaways": [
            "Pilot customers requested automated Slack notifications for assigned action items.",
            "High satisfaction with Gemini multilingual transcript accuracy."
        ],
        "action_items": [
            {"task": "Research Slack webhook integration for action item alerts", "owner": "Charlie", "deadline": "2026-11-28", "status": "Pending", "priority": "Low"},
            {"task": "Create customer feedback summary slide deck", "owner": "Frank", "deadline": "2026-11-23", "status": "In Progress", "priority": "Medium"}
        ]
    }
]

def seed_firestore():
    print(f"Connecting to Firestore for project: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection("meetings")

    for meeting in SAMPLE_MEETINGS:
        doc_id = meeting["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(meeting)
        print(f"✓ Seeded meeting: {doc_id} ('{meeting['title']}')")

    print(f"\nSuccessfully seeded {len(SAMPLE_MEETINGS)} meetings into 'meetings' collection.")

if __name__ == "__main__":
    seed_firestore()
