# Event Exporter

A Unity editor tool that exports SystemEvent ScriptableObjects into a structured JSON file for external analysis.

## Why this exists

Managing large numbers of event-based ScriptableObjects in Unity can make it difficult to:

- Analyze branching logic
- Validate event data consistency
- Export structured data for external tools

This tool provides a simple way to export all SystemEvent assets into a single JSON file.

## Features

- Exports all SystemEvent ScriptableObjects to JSON
- Accessible via Unity Tools menu
- Designed for narrative and event-driven systems
- Works with existing ScriptableObject workflows

## Installation

### Via Git URL

1. Open Unity Package Manager
2. Click "+"
3. Select "Add package from Git URL"
4. Enter:

https://github.com/mbripka/event-exporter.git

## Usage

1. Create or configure SystemEvent ScriptableObjects
2. In Unity, open:

Tools > Event Exporter

3. Run the export
4. Locate the generated JSON file

The exported JSON contains all event data in a structured format suitable for analysis pipelines.

## Structure

- Runtime/ → SystemEvent definitions
- Editor/ → Export tool
- Runtime/Events/ → Example or included assets

## Limitations

- Editor-only tool (not used at runtime)
- Assumes consistent SystemEvent schema
- Does not validate event logic beyond structure