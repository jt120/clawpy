import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# pytest -s tests/test_prompt.py::test_system_prompt
def test_system_prompt():
    import claw
    from claw import load_system_prompt, load_config, get_system_context
    current_dir = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace = current_dir
    config = load_config(workspace)
    system_context = get_system_context()
    system_prompt = load_system_prompt(current_dir, script_dir, config, system_context)
    print(system_prompt)
    
