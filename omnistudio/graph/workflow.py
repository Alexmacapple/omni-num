import os
import sqlite3
from datetime import datetime
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from graph.state import WorkflowState
from graph.nodes.import_node import import_scenario
from graph.nodes.assign_node import assign_voices_node
from graph.nodes.generate_node import generate_batch_node
from graph.nodes.export_node import export_zip_node
from graph.subgraphs.clean_loop import create_clean_subgraph
from graph.subgraphs.design_loop import create_design_subgraph

def prepare_clean(state: WorkflowState):
    return {
        "steps": state.get("steps") or [],
        "cleaning_mode": state.get("cleaning_mode", "auto"),
        "cleaning_validated": state.get("cleaning_validated", False),
        "llm_provider": state.get("llm_provider", "Albert Large 120B"),
        "domain_glossary": state.get("domain_glossary", {}),
        "correction_patterns": state.get("correction_patterns", {}),
        "correction_parentheses": state.get("correction_parentheses", {}),
        "correction_majuscules": state.get("correction_majuscules", {}),
        "decision": state.get("decision", ""),
        "iteration": state.get("iteration", 0),
    }

def finalize_clean(state):
    logs = []
    for step in state.get("steps", []):
        if step.get("cleaning_status") in ["cleaned", "validated"]:
            logs.append({
                "step_id": step.get("step_id"),
                "llm_provider": state.get("llm_provider"),
                "timestamp": datetime.now().isoformat()
            })
    return {
        "steps": state.get("steps", []),
        "cleaning_validated": state.get("decision") == "validated",
        "cleaning_log": logs,
        "iteration_count": 1
    }

def create_workflow(db_path: str = None):
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "omnistudio_checkpoint.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    # WAL mode for better concurrency (PRD-026)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    checkpointer = SqliteSaver(conn)
    
    workflow = StateGraph(WorkflowState)
    
    # Noeuds
    workflow.add_node("import", import_scenario)
    
    # Sub-graphs compilés (interrupts)
    clean_app = create_clean_subgraph()
    design_app = create_design_subgraph()
    
    workflow.add_node("prepare_clean", prepare_clean)
    workflow.add_node("clean", clean_app)
    workflow.add_node("finalize_clean", finalize_clean)
    workflow.add_node("design", design_app)
    workflow.add_node("assign", assign_voices_node)
    workflow.add_node("generate", generate_batch_node)
    workflow.add_node("export", export_zip_node)
    
    # Transitions
    workflow.add_edge(START, "import")
    workflow.add_edge("import", "prepare_clean")
    workflow.add_edge("prepare_clean", "clean")
    workflow.add_edge("clean", "finalize_clean")
    
    def route_after_clean(state: WorkflowState):
        if state.get("cleaning_validated") or state.get("decision") == "validated":
            return "design"
        return "prepare_clean"

    workflow.add_conditional_edges("finalize_clean", route_after_clean)
    
    def route_after_design(state: WorkflowState):
        if state.get("locked_voices"):
            return "assign"
        return "design"

    workflow.add_conditional_edges("design", route_after_design)
    
    workflow.add_edge("assign", "generate")
    workflow.add_edge("generate", "export")
    workflow.add_edge("export", END)
    
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["prepare_clean", "design", "assign", "generate", "export"]
    )

app = create_workflow()
