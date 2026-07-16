# Vice Studio Database

This database layer provides the initial persistence layer for the Vice Studio media platform.
It uses SQLite for local, file-based storage and is designed to support research, content drafting,
and publishing workflows.

## Purpose

The database stores structured records for:
- content sources and scraped articles
- extracted facts for validation and research
- topics and scripts for channel-specific content planning
- storyboards, generated videos, uploads, and analytics

## Table Relationships

- `sources` → `articles`: each article belongs to one source.
- `articles` → `facts`: each fact is traced back to a source article.
- `topics` → `scripts`: each script can be linked to one topic.
- `scripts` → `storyboards`: each storyboard can be associated with a script.
- `scripts` → `videos`: each video can be linked to a script.
- `videos` → `uploads`: each upload can be linked to a video.
- `videos` → `analytics`: analytics records can be attached to a video.

## Core Usage

The main helper module is `database/db.py`, which exposes functions for:
- opening a connection
- initializing the schema
- inserting sources, articles, facts, and topics
- listing the available tables

## Storage Location

The SQLite database file is stored at:
- `database/vice.db`
