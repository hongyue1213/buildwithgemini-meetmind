# My agent: MeetMind (會議智慧與知識庫特工)
One-liner: A conversational agent that helps teams process meeting audio and transcripts into structured notes and action items, organizing them into an indexed, searchable knowledge base of meeting records and tasks.

Tool coverage:
- Memory: Remembers user role/preferences (e.g. focus topics, preferred summary style), project contexts, and recurring team member identities across sessions.
- Tools:
  - Process meeting audio files (Gemini multimodal audio ingestion) or direct transcript text into structured minutes.
  - Extract and track action items, assignees, and deadlines.
  - Semantic search across indexed past meeting minutes and decisions.
  - Filter and retrieve action items by status, owner, or project.
- Catalog/UI:
  - Meeting catalog cards (title, date, attendees, topics, key takeaways).
  - Action items table (task, owner, deadline, priority, status).
- Image gen: Generates visual summary mind maps, concept diagrams, or milestone celebration banners for key meeting outcomes.
- Sandbox: Calculates meeting statistics (duration, speaker share, task completion rate and velocity).

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch (pick what fits): Code sandbox for team task & time analytics, Cloud Trace for latency tracking, Cloud Storage for audio & document persistence.
