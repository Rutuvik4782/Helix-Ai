# Helix AI — Legacy Python Modernizer

Helix AI is an intelligent, multi-agent assistant designed to automatically analyze, plan, refactor, and validate the modernization of legacy Python code (Python 2.x and early 3.x) to modern, standards-compliant Python 3 (such as Python 3.12).

It employs a hybrid architecture, combining **deterministic, rule-based checks** with a **fine-tuned Machine Learning model** for complex logic transformation, ambiguity resolution, and code rewriting.

---

## 🚀 Key Features

* **Multi-Agent Collaboration Workflow:**
  * **Analyzer Agent (`analyzer.py`):** Scans legacy code for deprecated syntax patterns (e.g., `print` statements, `xrange`, old exception bindings, `<>` operators).
  * **Planner Agent (`planner.py`):** Constructs a step-by-step migration plan.
  * **Suggester Agent (`suggester.py`):** Leverages LLM capabilities to suggest modern replacements for complex structures.
  * **Critic Agent (`critic.py`):** Reviews the suggestions and ranks risk levels.
  * **Validation Engine (`validation.py`):** Runs syntax validation and syntax checks to ensure the refactored code executes without errors.
* **Fine-Tuned ML Model Integration:** Powered by a customized adapter built on top of `Qwen2.5-Coder-1.5B-Instruct` fine-tuned specifically for legacy code migrations.
* **Intuitive Web UI:** Simple interactive dashboard built with Vanilla HTML, JavaScript, and Tailwind CSS to paste legacy code, run migrations, and view side-by-side diffs.

---

## 🛠️ Tech Stack

* **Backend:** FastAPI, Uvicorn
* **Frontend:** HTML5, Tailwind CSS, Vanilla JS
* **ML/AI:** PyTorch, Hugging Face Transformers, PEFT (LoRA), Unsloth (for fine-tuning)
* **Base Model:** `Qwen2.5-Coder-1.5B-Instruct`
* **Custom Adapter:** `nebula-modernizer-qwen25-1.5b`

---

## 🏁 Quick Start

### 1. Prerequisites
* Python 3.11 or higher
* Pip (Python package manager)

### 2. Setup Environment
Cloned the repository? Install dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-ml.txt
```

### 3. Run the Application
Start the FastAPI server in the background using the provided startup script:
```bash
bash start.sh
```
This launches Uvicorn on port `8000`. You can access the UI by opening your web browser to:
👉 **`http://localhost:8000`**

The server log is written to `server.log`, and its process ID (PID) is tracked in `server.pid`.

---

## 📂 Project Structure

```
Helix-Ai/
├── agents/             # Multi-Agent orchestrators
│   ├── analyzer.py     # Detects legacy code issues
│   ├── planner.py      # Establishes migration plan
│   ├── suggester.py    # Proposes modernized replacements
│   └── critic.py       # Validates & scores modifications
├── core/               # App logic
│   ├── ml_reasoner.py  # Loads base Qwen + LoRA adapter weights
│   ├── run_store.py    # Log/load migration history
│   └── validation.py   # Code syntax checks
├── ml/                 # Model training files
│   ├── models/         # Fine-tuned adapter weights
│   ├── data/           # Dataset mixtures
│   └── README.md       # ML training workflow documentation
├── static/             # Frontend assets (CSS & JS)
├── templates/          # HTML views (index.html, etc.)
├── main.py             # FastAPI entrypoint
└── start.sh            # Background process starter
```
