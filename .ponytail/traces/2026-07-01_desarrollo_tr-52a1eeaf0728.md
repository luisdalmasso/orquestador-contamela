---
trace_id: tr-52a1eeaf0728
timestamp: "2026-07-01T13:08:04-0300"
circuit: desarrollo
model: ""
status: error
duration_ms: 0
tokens_used:
  input: 0
  output: 0
  total: 0
tool_calls_count: 1
errors_count: 1
sourcebot_hits:
  - path: app/main.py
    line: 1
tool_calls:
  - name: run_salvar
    status: success
    latency_ms: 100
errors:
  - "AssertionError: assert 1 == 3
 +  where 1 = len([{'data': {'text': 'hi'}, 'timestamp': 1782922084809, 'type': 'omp_message_update'}])
 +    where [{'data': {'text': 'hi'}, 'timestamp': 1782922084809, 'type': 'omp_message_update'}] = <app.openhands_agent.ponytail.PonytailTrace object at 0x7c13fd991cd0>.events"
---

# 🔍 Traza Ponytail: `tr-52a1eeaf0728`

Modo: `DESARROLLO` | Estado: 🔴 **ERROR** | Fecha: `2026-07-01T13:08:04-0300`

## 🗺️ Flujo de Ejecución

Este diagrama se renderiza automáticamente en GitHub:

```mermaid
sequenceDiagram
    autonumber
    Client->>Router: POST /v1/chat/completions (circuit: desarrollo)
    Router->>Ponytail: enter context
    par Context build
        Ponytail->>Sourcebot: search (top-5)
        Sourcebot-->>Ponytail: paths
    end
    Ponytail->>Omp: append_system_prompt + user_task
    Omp-->>Ponytail: turn_start
    loop 1 tool calls
        Omp->>MCP: call tool (name, args)
        MCP->>Backend: dispatch handler
        Backend-->>MCP: result
        MCP-->>Omp: result
    end
    Omp-->>Ponytail: agent_end (text)
    Ponytail->>Backend: mcp_record_trace
    Backend->>Backend: write .ponytail/traces/<id>.md
    Backend->>Backend: git add + commit (async)
    Ponytail-->>Client: OpenAI response
```

## 💬 Mensajes

### User (input)
```
test
```

## 🔧 Tool Calls (1)

### 1. `run_salvar`
- **status:** success
- **latency:** 100ms
- **args:**
```json
{"x": 1}
```
- **result:**
```json
{"ok": true}
```

## 📡 Sourcebot Hits

- `app/main.py:1`

## ❌ Errors

1. `AssertionError: assert 1 == 3
 +  where 1 = len([{'data': {'text': 'hi'}, 'timestamp': 1782922084809, 'type': 'omp_message_update'}])
 +    where [{'data': {'text': 'hi'}, 'timestamp': 1782922084809, 'type': 'omp_message_update'}] = <app.openhands_agent.ponytail.PonytailTrace object at 0x7c13fd991cd0>.events`
