# Retrospective notes

These decisions were written down after the code worked. They are not a prior specification.

- Eager "always search, then ask the model" was rejected while testing the greeting path. The model is offered every tool and can answer with none.
- Natural-language confirmation was rejected because an injected "yes" would file a ticket. The button calls `Store.confirm` with a server-side token the model never receives.
- The fallback path exists so the VPN demo still runs in a checkout that has no `.env`.
- TF-IDF over eight markdown files was enough. A vector database would have added a service this machine does not need.
- Answer quality in the offline suite is retrieval rank plus term overlap with the retrieved excerpts. It is not a claim about a live Claude deployment.
