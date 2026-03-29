# Requirements

---

## Backend - BHAVESH

- [ ] Store faces
- [ ] Store context for the faces (RAW from frontend) (Only last interaction)
  - [ ] Last interaction transcript
  - [ ] First conversation is permanent
- [ ] Store users (App-wise)
  - [ ] Sync between App and web-app

## API - HARSHITH

- [ ] Ingest transcript of audio use Whisper to convert to text
  - [ ] Store in Supabase
- [ ] Ingest video and convert to json
- [ ] Attach face with UUID
- [ ] Generate AI summary for context
- [ ] Do actual face recognition

## Frontend - Web - SIDDHANTH

- [ ] Login/Register
- [ ] Recognize live video
- [ ] Display context of face (AI summary)
  - [ ] Short phrase from first interaction
  - [ ] longer summary from last interaction
- [ ] Ingest video for face recognition
- [ ] Ingest audio for context generation

## Frontend - Mobile - VAKUL

- [ ] Login/Register
- [ ] Recognize faces through pictures
  - [ ] Upload picture
  - [ ] Capture live
- [ ] Display AI sumamry context for existing faces

# Architecture

---

```mermaid
flowchart TD

A[Flutter Mobile App] -->|Capture Image| B[FastAPI Backend]

C[Angular Web Dashboard] -->|Live Image Feed| B

B --> D[Face Detection - OpenCV]
D --> E[Face Embedding Model]

E --> F[Compare with Stored Embeddings]

F -->|Match Found| G[Fetch Person Data from Supabase]
F -->|No Match| H[Unknown Person]

G --> I[Ollama - AI Model]
I --> J[Generate Contextual Reminder]

J --> K[Send Response to Mobile App]

K --> L[Display + Voice Output]

B --> M[Supabase DB]
M --> F
M --> G
```

```mermaid
flowchart LR
    subgraph P1["Phase 1 · Capture"]
        A[Flutter App\nMobile]
        B[Angular\nWeb Dashboard]
        C[FastAPI\nBackend]
        A --> C
        B --> C
    end

    subgraph P2["Phase 2 · Detection"]
        D[OpenCV\nFace Detection]
    end

    subgraph P3["Phase 3 · Recognition"]
        E[Embedding\nFace Model]
        F[Compare\nStored Embeddings]
        G[(Supabase\nDB / Embeddings)]
        H[Unknown]
        E --> F
        G --> F
        F -- no match --> H
    end

    subgraph P4["Phase 4 · Lookup & AI"]
        I[Fetch Data\nSupabase Person]
        J[Ollama\nLocal AI Model]
        I --> J
    end

    subgraph P5["Phase 5 · Output"]
        K[Reminder\nContextual AI]
        L[Send\nTo Mobile App]
        M[Display\n+ Voice Output]
        K --> L --> M
    end

    P1 --> P2
    C --> D
    D --> E
    F -- match --> I
    J --> K
```

# Tech Stack

---

- [ ] Web App Frontend - Angular
- [ ] Mobile App - Flutter
- [ ] API - FastAPI
- [ ] Backend - Supabase
- [ ] AI - Ollama
- [ ] CV - cv2, face_recognition
