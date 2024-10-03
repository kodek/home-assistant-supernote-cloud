# home-assistant-supernote-cloud

Home Assistant Custom Component dedicated to the excellent Ratta Supernote products.

This custom component efficiently synchronizes a backup of your notebook to your
local storage and exposes the contents through the media player.

The motivation is to use with [Journal Assistant](https://github.com/allenporter/home-assistant-journal-assistant) and [Supernote LLM](https://github.com/allenporter/supernote-llm/).

Library for efficient backup based on:

- https://github.com/bwhitman/supernote-cloud-python/
- https://github.com/adrianba/supernote-cloud-api/
- https://github.com/colingourlay/supernote-cloud-api/

## Development plan

- [x] Authentication library and configuration flow
- [x] Media player skeleton of directory contents
- [ ] Tests for store
- [ ] Syncing of note contents
- [ ] handle non .note files
- [ ] Extracting png content
- [ ] async iterator to page through contents
- [ ] concurrency fixes
