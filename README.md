# Supernote Cloud Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![test_suite](https://github.com/allenporter/home-assistant-supernote-cloud/actions/workflows/test.yaml/badge.svg)](https://github.com/allenporter/home-assistant-supernote-cloud/actions)

Bring your Ratta Supernote e-ink tablet into your smart home ecosystem. This integration connects Home Assistant to your **Supernote Cloud Account**, supporting both the official, original Supernote Cloud service and your own self-hosted **[Supernote Private Cloud Server](https://github.com/allenporter/supernote)**. It allows you to own or access your notes, monitor device cloud capacity, view notebook pages dynamically, and interact with your handwritten notes using Large Language Models (LLMs) and Home Assistant Assist.

---

## 🌟 Key Features

### 🧠 AI & LLM Assistants (The Novel Layer)

This integration registers custom tools with Home Assistant's LLM engine, enabling conversational agents (such as Google Gemini in Home Assistant) to read, search, and answer questions about your notes.

- **Semantic Search (`search_supernote`)**: Allows LLMs to search for concepts across your handwritten notebook library using vector similarity search.
- **Notebook Transcripts (`get_supernote_transcript`)**: Exposes the text transcript of any notebook or journal to the model.
- **Companion Integrations**: Pairs perfectly with **[Journal Assistant](https://github.com/allenporter/home-assistant-journal-assistant)** and **[Supernote LLM](https://github.com/allenporter/supernote-llm/)** to convert handwritten bullet journals into structured calendar events and PKM insights.

### 🖼️ Dynamic Notebook Rendering (Media Source)

Exposes your notebook library via Home Assistant's native **Media Browser**.

- Browse folders and files synced from your tablet.
- View notebook pages rendered dynamically on-the-fly as `.png` images directly in the Home Assistant UI or cast them to media players.

### 📊 Storage Capacity Sensors

Keep track of your cloud account's storage capacity. The integration registers four sensors polled automatically every 30 minutes:

- **Storage Used** (in GB)
- **Storage Total** (in GB)
- **Storage Free** (in GB)
- **Storage Usage Ratio** (in %)

---

## 🔒 Self-Hosted Private Cloud vs. Official Cloud

This component supports two sync options:

- **Official Cloud**: By default, it connects to the official, original Supernote Cloud service (using your standard Supernote credentials).
- **Self-Hosted Server**: If you want complete data privacy and local ownership, it integrates seamlessly with **[allenporter/supernote](https://github.com/allenporter/supernote)**, a lightweight, SQLite-backed private cloud server.
  - **Privacy-First**: No data is leaked to external corporate clouds. Your notes sync directly to a database in your home lab or NAS.
  - **Highly Efficient**: Consumes less than ~200MB of memory at idle, making it perfect for running on a low-power home server.

---

## 🚀 Getting Started

### Installation via HACS

- Open **HACS** in Home Assistant.
- Click the three dots in the top right and select **Custom repositories**.
- Add `https://github.com/allenporter/home-assistant-supernote-cloud` with category **Integration**.
- Click **Download**.
- Restart Home Assistant.

### Configuration

- Go to **Settings** -> **Devices & Services** -> **Add Integration**.
- Search for **Supernote Cloud**.
- Enter your credentials (username/phone number and password).
- By default, the **Supernote Private Cloud URL** is set to the official cloud URL. If you are using a self-hosted server, change this to your server's local URL.
- Follow the setup flow (including entering the SMS verification code if applicable).

---

## 🛠️ Local Development

### Pre-requisites

Set up the python virtual environment and bootstrap development scripts:

```bash
$ script/bootstrap
$ script/setup
```

### Running the Dev Server

Launch Home Assistant locally with the custom component loaded:

```bash
$ script/server
```

### Running Tests

We use `pytest` for unit testing. Run the test suite:

```bash
$ .venv/bin/pytest
```
