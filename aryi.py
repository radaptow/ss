import os
import requests
import json

OLLAMA_HOST = "http://100.115.1.71:11434"

# ==========================================
# 🎚️ SWITCH MAESTRO DE REALIDAD
# ==========================================
REAL_CODE_MODE = True 

def get_available_models():
    try:
        url = f"{OLLAMA_HOST}/api/tags"
        response = requests.get(url, timeout=300)
        if response.status_code == 200:
            models_data = response.json().get("models", [])
            return [m["name"] for m in models_data]
    except Exception as e:
        print(f"❌ Error al conectar con Ollama: {e}")
    return []

def select_model(models, keywords, fallback):
    for keyword in keywords:
        for model in models:
            if keyword in model.lower():
                return model
    return fallback if fallback in models else (models[0] if models else None)

def scan_specific_file(filename="aryi2.py"):
    """Lee un archivo específico de forma limpia para no saturar de tokens el contexto."""
    print(f"📂 Leyendo archivo clave: '{filename}'...")
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            return f"Error al leer el archivo: {e}"
    return "No se encontró el archivo de código base."

class AIAgentActor:
    def __init__(self, name, model_name, role_persona):
        self.name = name
        self.model_name = model_name
        self.persona = role_persona

    def think(self, context_prompt):
        url = f"{OLLAMA_HOST}/api/generate"
        full_prompt = f"{self.persona}\n\nContexto / Código:\n{context_prompt}\n\nResponde de forma concisa y profesional según tu rol:"

        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": True
        }

        print(f"\n[{self.name}] Usando '{self.model_name}'...")
        print("-" * 50)
        print(f"--- {self.name} dice: ---")

        full_response = ""
        try:
            response = requests.post(url, json=payload, stream=True, timeout=180)
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        body = json.loads(line.decode('utf-8'))
                        chunk = body.get("response", "")
                        print(chunk, end="", flush=True)
                        full_response += chunk
                        if body.get("done", False):
                            break
                print("\n" + "-" * 50)
                return full_response
            else:
                error_msg = f"❌ Error HTTP {response.status_code}: {response.text}"
                print(error_msg)
                return error_msg
        except Exception as e:
            err = f"❌ Excepción: {str(e)}"
            print(err)
            return err

if __name__ == "__main__":
    print(f"=== INICIANDO PIPELINE OPTIMIZADO (REAL_CODE_MODE: {REAL_CODE_MODE}) ==-\n")
    
    available_models = get_available_models()
    if not available_models:
        print("❌ No hay conexión con el clúster.")
        exit(1)

    # Selección optimizada para evitar sobrecarga de VRAM
    client_model = select_model(available_models, ["gemma2", "nemotron"], available_models[0])
    dev_model = select_model(available_models, ["qwen2.5-coder:7b", "coder"], available_models[0])
    qa_model = select_model(available_models, ["gemma2", "bonsai"], available_models[0])
    reviewer_model = select_model(available_models, ["qwen3.8", "nemotron"], available_models[0])
    git_model = select_model(available_models, ["qwen2.5-coder:0.5b"], available_models[0])

    print(f"-> 🏢 Product Owner: {client_model}")
    print(f"-> 💻 Desarrollador: {dev_model}")
    print(f"-> 🧪 Tester/QA: {qa_model}")
    print(f"-> 🧐 Reviewer: {reviewer_model}")
    print(f"-> 🤖 GitOps Bot: {git_model}\n" + "="*50)

    if REAL_CODE_MODE:
        code_content = scan_specific_file("aryi2.py") # Analizamos nuestro propio script de agentes
        
        client_persona = "Eres un Product Owner analítico. Revisas el script de automatización actual y pides una optimización o nueva característica."
        developer_persona = "Eres un Desarrollador Senior en Python. Analiza el código proporcionado y escribe mejoras limpias y funcionales."
        qa_persona = "Eres un QA estricto. Revisa el código del desarrollador buscando posibles errores de sintaxis o fallas lógicas."
        reviewer_persona = "Eres el Tech Lead. Evalúa el código y da el veredicto final para producción."
        git_persona = "Eres el Bot de Git. Redacta los mensajes de commit profesionales."
        
        base_input = f"Aquí está el código fuente actual:\n{code_content}\n\nPropón y aplica una mejora o refactorización limpia para este script."
    else:
        client_persona = "Eres un cliente tiránico."
        developer_persona = "Eres un dev junior."
        qa_persona = "Eres un QA sarcástico."
        reviewer_persona = "Eres un Tech Lead amargado."
        git_persona = "Eres un bot de Git."
        base_input = "Necesito un sistema rápido."

    # --- EJECUCIÓN DEL PIPELINE FLUÍDO ---
    po_output = client_ai = AIAgentActor("Product Owner", client_model, client_persona).think(base_input)
    dev_output = AIAgentActor("Desarrollador", dev_model, developer_persona).think(f"Directiva del PO:\n{po_output}\nImplementa la mejora en código.")
    qa_output = AIAgentActor("Tester QA", qa_model, qa_persona).think(f"Audita este código:\n{dev_output}")
    reviewer_output = AIAgentActor("Reviewer", reviewer_model, reviewer_persona).think(f"Code review de:\n{qa_output}")
    AIAgentActor("GitOps Bot", git_model, git_persona).think(f"Prepara los commits basados en:\n{reviewer_output}")