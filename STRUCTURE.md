# Structure du projet — Chatbot Smartovate

Explication complète de chaque dossier et fichier du projet.

---

## Vue d'ensemble

```
Chatbot-Smartovate/
└── backend/
    ├── app/
    │   ├── bot/
    │   ├── engine/
    │   ├── models/
    │   ├── routes/
    │   ├── services/
    │   ├── __init__.py
    │   ├── config.py
    │   └── main.py
    ├── .env
    ├── .env.example
    ├── .gitignore
    └── requirements.txt
```

---

## Dossier racine — `backend/`

C'est le dossier principal du serveur. Il contient tout le code Python qui fait fonctionner le chatbot.
Quand on lance le serveur, on se place dans ce dossier.

---

## Dossier `backend/app/`

C'est le cœur de l'application. Tout le code métier est ici.
Il contient 5 sous-dossiers, chacun avec une responsabilité bien précise.

---

### `app/bot/`

**Rôle :** Contient la classe principale du Bot Framework SDK.

Ce dossier a été créé pour préparer l'intégration avec Azure Bot Service.
La classe `SmartovateBot` hérite de `ActivityHandler` (fourni par le Bot Framework SDK Python).
Elle reçoit les messages des utilisateurs et les transmet au `BotEngine` pour traitement.

| Fichier | Description |
|---|---|
| `__init__.py` | Marque le dossier comme un package Python (fichier obligatoire) |
| `smartovate_bot.py` | Classe `SmartovateBot` — reçoit les messages, appelle `BotEngine`, retourne la réponse |

**Communique avec :** `engine/bot_engine.py`, `routes/bot_messages.py`

**Statut :** Préparé — sera activé lors de la connexion à Azure Bot Service.

---

### `app/engine/`

**Rôle :** Contient le BotEngine, l'orchestrateur central du chatbot.

C'est le composant le plus important de l'application.
Il coordonne tous les services : il reçoit un message, appelle Azure AI Search pour trouver des documents pertinents, envoie tout à Azure OpenAI pour générer une réponse, et décide si un transfert vers un agent humain est nécessaire.

Aucune route n'appelle directement Azure OpenAI — tout passe par le BotEngine.

| Fichier | Description |
|---|---|
| `__init__.py` | Marque le dossier comme un package Python |
| `bot_engine.py` | Classe `BotEngine` — orchestre le pipeline complet de traitement des messages |

**Communique avec :** `services/azure_openai_service.py`, `services/azure_ai_search_service.py`, `models/conversation.py`

**Statut :** Partiellement implémenté — appelle Azure OpenAI. Azure AI Search et Handoff seront ajoutés aux prochaines étapes.

---

### `app/models/`

**Rôle :** Contient la définition de toutes les entités du domaine métier.

Ces fichiers ne font rien par eux-mêmes — ils décrivent la forme des données utilisées dans l'application. Chaque fichier correspond à une entité définie dans les diagrammes UML du projet.

| Fichier | Entité représentée | Description |
|---|---|---|
| `__init__.py` | — | Marque le dossier comme un package Python |
| `utilisateur.py` | `Utilisateur` | Un utilisateur du système avec son rôle : Client, Agent Support ou Administrateur |
| `conversation.py` | `Conversation` | Une session de chat avec son état : Initiée, EnAttenteMessage, EnTraitement, EnAttenteAgent, PriseEnChargeAgent, Clôturée |
| `message.py` | `Message` | Un message individuel dans une conversation — envoyé par un utilisateur, l'IA ou un agent humain |
| `handoff_request.py` | `HandoffRequest` | Une demande de transfert vers un agent humain — créée quand l'IA ne peut pas répondre ou quand l'utilisateur le demande |
| `agent_humain.py` | `AgentHumain` | Un agent du support humain avec sa disponibilité |
| `document.py` | `Document` | Un document de la base de connaissances utilisé par Azure AI Search pour le RAG |

**Communique avec :** `engine/bot_engine.py`, `routes/chat.py`, `routes/agent.py`, `routes/admin.py`

---

### `app/routes/`

**Rôle :** Contient les endpoints de l'API, organisés par acteur.

Chaque fichier regroupe les URLs accessibles pour un acteur précis du système.
C'est ici que les requêtes HTTP arrivent en premier avant d'être traitées.

| Fichier | Acteur | Endpoints disponibles |
|---|---|---|
| `__init__.py` | — | Marque le dossier comme un package Python |
| `chat.py` | Client | `POST /api/chat/message`, `POST /api/chat/handoff`, `GET /api/chat/conversation/{id}`, `POST /api/chat/test-openai` |
| `agent.py` | Agent Support | `GET /api/agent/queue`, `POST /api/agent/takeover/{id}`, `POST /api/agent/reply/{id}` |
| `admin.py` | Administrateur | `POST /api/admin/documents/index`, `GET /api/admin/documents`, `GET /api/admin/metrics` |
| `bot_messages.py` | Azure Bot Service | `POST /api/messages` — point d'entrée Bot Framework |

**Communique avec :** `engine/bot_engine.py`, `services/azure_openai_service.py`, `bot/smartovate_bot.py`

---

### `app/services/`

**Rôle :** Contient les connecteurs vers les services Azure externes.

Chaque fichier encapsule toute la logique de communication avec un service Azure.
Ils ne sont jamais appelés directement par les routes — ils passent par le BotEngine.

| Fichier | Service Azure | Description |
|---|---|---|
| `__init__.py` | — | Marque le dossier comme un package Python |
| `azure_openai_service.py` | Azure OpenAI (gpt-4o) | Envoie les messages à gpt-4o et retourne la réponse. **Opérationnel et testé.** |
| `azure_ai_search_service.py` | Azure AI Search | Recherche les documents pertinents dans la base de connaissances pour le RAG. **Squelette — sera implémenté à l'étape RAG.** |

**Communique avec :** `config.py` (pour les clés API et endpoints), Azure sur le cloud Microsoft

---

### `app/__init__.py`

Fichier vide qui indique à Python que le dossier `app` est un package.
Sans ce fichier, Python ne pourrait pas importer les modules de l'application.

---

### `app/config.py`

**Rôle :** Gestionnaire centralisé de toute la configuration de l'application.

Ce fichier lit automatiquement toutes les variables du fichier `.env` au démarrage.
Il les rend disponibles à tous les autres fichiers via une instance unique (`get_settings()`).

Aucune valeur sensible n'est écrite directement dans le code — tout passe par ce fichier.

**Variables gérées :**
- Azure OpenAI : endpoint, clé API, deployment, température
- Azure AI Search : endpoint, clé API, nom de l'index
- Azure Bot Service : MicrosoftAppId, MicrosoftAppPassword
- Application : nom, version, seuil de confiance pour le handoff

**Communique avec :** `.env` (source des valeurs), tous les services et le BotEngine (consommateurs)

---

### `app/main.py`

**Rôle :** Point d'entrée de l'application FastAPI.

C'est le premier fichier exécuté quand on lance le serveur.
Il crée l'application FastAPI, configure les autorisations CORS (pour que le frontend puisse communiquer avec le backend), et enregistre toutes les routes.

**Communique avec :** `config.py`, tous les fichiers dans `routes/`

---

## Fichiers à la racine de `backend/`

### `.env`

**Rôle :** Fichier de configuration local contenant toutes les valeurs sensibles.

C'est ici que tu mets ta vraie clé API Azure OpenAI, les endpoints, etc.
Ce fichier n'est **jamais** envoyé sur GitHub grâce au `.gitignore`.
Chaque développeur a son propre `.env` en local.

**Contenu actuel :**
- Clé API Azure OpenAI ✅ configurée
- Endpoint Azure OpenAI ✅ configuré
- Deployment gpt-4o ✅ configuré
- Azure AI Search : vide (à configurer à l'étape RAG)
- MicrosoftAppId / Password : vide (à configurer lors de la connexion Azure Bot Service)

---

### `.env.example`

**Rôle :** Template public du fichier `.env`.

Contient exactement les mêmes variables que `.env` mais sans aucune vraie valeur.
Il est partageable publiquement — il sert de mode d'emploi pour tout nouveau développeur qui clone le projet.

---

### `.gitignore`

**Rôle :** Liste des fichiers et dossiers que Git ne doit jamais envoyer sur GitHub.

Contient notamment :
- `.env` — pour protéger les clés API
- `__pycache__/` — fichiers compilés Python générés automatiquement
- `venv/` — environnement virtuel Python

---

### `requirements.txt`

**Rôle :** Liste de toutes les bibliothèques Python nécessaires au projet.

Pour installer toutes les dépendances d'un coup :
```bash
pip install -r requirements.txt
```

**Bibliothèques principales :**

| Bibliothèque | Rôle |
|---|---|
| `fastapi` | Framework web Python pour créer l'API REST |
| `uvicorn` | Serveur qui exécute l'application FastAPI |
| `openai` | SDK officiel pour appeler Azure OpenAI (gpt-4o) |
| `pydantic-settings` | Gestion et validation des variables d'environnement |
| `botbuilder-core` | SDK Bot Framework Python — classe de base du bot |
| `botframework-connector` | Authentification et communication avec Azure Bot Service |
| `azure-search-documents` | SDK pour Azure AI Search (RAG) |
| `python-dotenv` | Lecture du fichier `.env` |

---

## Résumé visuel — qui parle à qui

```
Utilisateur
    │
    ▼
routes/chat.py  ──────────────────────────────┐
routes/bot_messages.py → bot/smartovate_bot.py │
    │                                          │
    ▼                                          │
engine/bot_engine.py  ◄────────────────────────┘
    │               │
    ▼               ▼
services/           services/
azure_openai_       azure_ai_search_
service.py ✅       service.py ⏳
    │
    ▼
Azure OpenAI
(gpt-4o) ✅
```

**Légende :**
- ✅ Opérationnel et testé
- ⏳ Squelette — à implémenter à la prochaine étape

---

## État d'avancement

| Composant | État |
|---|---|
| Structure du projet | ✅ Complète |
| Azure OpenAI (gpt-4o) | ✅ Connecté et testé |
| BotEngine (sans RAG) | ✅ Fonctionnel |
| Bot Framework SDK | ✅ Intégré (en attente Azure Bot Service) |
| Azure AI Search | ⏳ À implémenter |
| Pipeline RAG | ⏳ À implémenter |
| Handoff vers agent humain | ⏳ À implémenter |
| Frontend React | ⏳ À créer |
| Déploiement Azure App Service | ⏳ À faire |
