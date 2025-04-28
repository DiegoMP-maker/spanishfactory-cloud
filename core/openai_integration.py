# En core/openai_integration.py, busca la función process_with_assistant
# y encuentra el bloque donde se inicia la ejecución del asistente:

# Busca este código:
run_response = assistants_client._api_request(
    "POST", 
    f"/threads/{thread_id}/runs", 
    data={
        "assistant_id": assistant_id,
        "tools": assistant_functions  # Añadir funciones disponibles
    }
)

# Y reemplázalo por:
run_response = assistants_client._api_request(
    "POST", 
    f"/threads/{thread_id}/runs", 
    data={
        "assistant_id": assistant_id,
        # Modificamos cómo pasamos las tools para que coincida con el formato esperado por la API v2
        "tools": [
            {"type": "code_interpreter"},  # Incluir code_interpreter para asegurar compatibilidad
            {"type": "retrieval"},         # Incluir retrieval para compatibilidad con vector store
            {"type": "function", "function": func["function"]} 
            for func in assistant_functions 
            if func["type"] == "function"
        ]
    }
)
