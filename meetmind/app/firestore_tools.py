"""Firestore read and write tools for MeetMind agent.

Hardcodes the GCP project ID to avoid Agent Platform project number resolution issues.
"""
from typing import Any, Dict, List, Optional
import datetime
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-8581f7539bcb"
_db: Optional[firestore.Client] = None


def get_db() -> firestore.Client:
    """Lazily initializes and returns the Firestore client."""
    global _db
    if _db is None:
        _db = firestore.Client(project=PROJECT_ID)
    return _db


def list_meetings(limit: int = 10) -> List[Dict[str, Any]]:
    """Lists recent meetings stored in the Firestore knowledge base.

    Args:
        limit: Maximum number of meetings to return (default: 10).

    Returns:
        A list of meeting summaries containing id, title, date, attendees, and topics.
    """
    try:
        db = get_db()
        docs = db.collection("meetings").limit(limit).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            results.append({
                "id": doc.id,
                "title": data.get("title", "Untitled Meeting"),
                "date": data.get("date", "Unknown Date"),
                "attendees": data.get("attendees", []),
                "topics": data.get("topics", []),
            })
        return results
    except Exception as e:
        return [{"error": f"Failed to list meetings: {str(e)}"}]


def get_meeting_details(meeting_id: str) -> Dict[str, Any]:
    """Retrieves full details of a specific meeting from Firestore, including summary and action items.

    Args:
        meeting_id: The unique identifier of the meeting (e.g., 'meet-20261118-ai-roadmap').

    Returns:
        A dictionary containing full meeting details, summary, key takeaways, and action items.
    """
    try:
        db = get_db()
        doc = db.collection("meetings").document(meeting_id).get()
        if not doc.exists:
            return {"error": f"Meeting with ID '{meeting_id}' not found."}
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    except Exception as e:
        return {"error": f"Failed to fetch meeting '{meeting_id}': {str(e)}"}


def search_meetings(keyword: str) -> List[Dict[str, Any]]:
    """Searches meetings in Firestore by keyword in title, summary, or topics.

    Args:
        keyword: The term to search for (e.g., 'budget', 'roadmap', 'Slack').

    Returns:
        A list of matching meetings with id, title, date, summary snippet, and topics.
    """
    try:
        db = get_db()
        docs = db.collection("meetings").stream()
        keyword_lower = keyword.lower()
        matches = []
        for doc in docs:
            data = doc.to_dict()
            title = data.get("title", "")
            summary = data.get("summary", "")
            topics = data.get("topics", [])
            topics_str = " ".join(topics)

            if (keyword_lower in title.lower() or
                keyword_lower in summary.lower() or
                keyword_lower in topics_str.lower()):
                matches.append({
                    "id": doc.id,
                    "title": title,
                    "date": data.get("date", ""),
                    "summary": summary[:200] + ("..." if len(summary) > 200 else ""),
                    "topics": topics,
                    "action_item_count": len(data.get("action_items", []))
                })
        return matches
    except Exception as e:
        return [{"error": f"Failed to search meetings: {str(e)}"}]


def save_meeting(
    title: str,
    date: str,
    attendees: List[str],
    summary: str,
    topics: List[str],
    key_takeaways: List[str],
    action_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Saves a new meeting record and action items into Firestore.

    Args:
        title: The title of the meeting.
        date: Date of the meeting (YYYY-MM-DD format).
        attendees: List of participant names and roles.
        summary: Structured summary of what was discussed.
        topics: List of topics or tags covered in the meeting.
        key_takeaways: List of key decisions or conclusions.
        action_items: List of dictionaries, each containing 'task', 'owner', 'deadline', 'status', and 'priority'.

    Returns:
        A dictionary confirming creation with the assigned meeting ID.
    """
    try:
        db = get_db()
        safe_date = date.replace("-", "") if date else datetime.date.today().strftime("%Y%m%d")
        safe_title = "".join(c for c in title.lower() if c.isalnum() or c in (" ", "_", "-")).replace(" ", "-")[:30]
        doc_id = f"meet-{safe_date}-{safe_title}"

        record = {
            "id": doc_id,
            "title": title,
            "date": date or datetime.date.today().isoformat(),
            "attendees": attendees,
            "summary": summary,
            "topics": topics,
            "key_takeaways": key_takeaways,
            "action_items": action_items,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        db.collection("meetings").document(doc_id).set(record)
        return {"status": "success", "meeting_id": doc_id, "message": f"Meeting '{title}' saved successfully."}
    except Exception as e:
        return {"status": "error", "error": f"Failed to save meeting: {str(e)}"}


def list_action_items(owner: str = "", status: str = "") -> List[Dict[str, Any]]:
    """Retrieves and filters action items across all meetings in Firestore.

    Args:
        owner: Optional filter by owner or assignee name (case-insensitive substring match).
        status: Optional filter by status ('Pending', 'In Progress', 'Completed').

    Returns:
        A list of action items with task description, owner, deadline, status, priority, and meeting title.
    """
    try:
        db = get_db()
        docs = db.collection("meetings").stream()
        results = []
        owner_lower = owner.lower() if owner else ""
        status_lower = status.lower() if status else ""

        for doc in docs:
            data = doc.to_dict()
            meeting_title = data.get("title", "Untitled")
            meeting_id = doc.id
            items = data.get("action_items", [])
            for item in items:
                item_owner = item.get("owner", "")
                item_status = item.get("status", "")

                if owner_lower and owner_lower not in item_owner.lower():
                    continue
                if status_lower and status_lower != item_status.lower():
                    continue

                results.append({
                    "meeting_id": meeting_id,
                    "meeting_title": meeting_title,
                    "task": item.get("task", ""),
                    "owner": item_owner,
                    "deadline": item.get("deadline", ""),
                    "status": item_status,
                    "priority": item.get("priority", "Medium")
                })
        return results
    except Exception as e:
        return [{"error": f"Failed to list action items: {str(e)}"}]


def update_action_item_status(
    task_keyword: str,
    new_status: str,
    meeting_id: str = "",
) -> Dict[str, Any]:
    """Updates the status of an action item in Firestore.

    Args:
        task_keyword: Keyword or description of the task to update (e.g., 'Firestore', 'Slack').
        new_status: The new status ('Pending', 'In Progress', 'Completed').
        meeting_id: Optional meeting ID if known. If empty, searches across all meetings.

    Returns:
        A dictionary with the result of the update operation.
    """
    try:
        db = get_db()
        keyword_lower = task_keyword.lower()

        if meeting_id:
            doc = db.collection("meetings").document(meeting_id).get()
            docs = [doc] if doc.exists else []
        else:
            docs = list(db.collection("meetings").stream())

        updated_items = []
        for doc in docs:
            data = doc.to_dict()
            items = data.get("action_items", [])
            modified = False

            for item in items:
                if keyword_lower in item.get("task", "").lower():
                    old_status = item.get("status", "")
                    item["status"] = new_status
                    modified = True
                    updated_items.append({
                        "meeting_id": doc.id,
                        "task": item.get("task", ""),
                        "owner": item.get("owner", ""),
                        "old_status": old_status,
                        "new_status": new_status,
                    })

            if modified:
                db.collection("meetings").document(doc.id).update({"action_items": items})

        if updated_items:
            return {"status": "success", "updated_count": len(updated_items), "updated_items": updated_items}
        return {"status": "not_found", "message": f"No action item matching '{task_keyword}' was found."}
    except Exception as e:
        return {"status": "error", "error": f"Failed to update action item: {str(e)}"}

