# Architecture (v0)

## FR

Ce document fixe la base pour construire un système efficace, maintenable et extensible.

### Couches
- `Transport`: HTTP + WebSocket (FastAPI)
- `Domain`: commandes robot, sécurité, état mission
- `Adapters`: liaison Roomba (Bluetooth/Serial/WiFi bridge)
- `Observability`: logs structurés, métriques, événements

### Principes
- Boucle de contrôle déterministe côté serveur
- API idempotente pour commandes critiques
- Sécurité par défaut: timeout, heartbeat, stop d'urgence
- Dégradation gracieuse (fallback manuel)

## EN

This document defines the foundation for an efficient, maintainable and extensible system.

### Layers
- `Transport`: HTTP + WebSocket (FastAPI)
- `Domain`: robot commands, safety, mission state
- `Adapters`: Roomba connectivity (Bluetooth/Serial/WiFi bridge)
- `Observability`: structured logs, metrics, events

### Principles
- Deterministic control loop on server side
- Idempotent API for critical commands
- Safe-by-default: timeout, heartbeat, emergency stop
- Graceful degradation (manual fallback)
