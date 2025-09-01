from typing import Dict, Any


class ToolBase:
    """Base class for all tools"""

    name: str = "base_tool"
    description: str = "Base tool for all tools"

    def run(self, args: Dict[str, Any]) -> str:
        """Run the tool"""
        raise NotImplementedError("You must implement run()")

    def parse_output(self, raw_output: Any) -> Any:
        """Parse output to JSON/struct"""
        return raw_output

    def to_langgraph_node(self, input_key: str, output_key: str):
        def node(state: dict) -> dict:
            if input_key not in state:
                raise ValueError(f"Missing required input: {input_key}")
            result = self.run({input_key: state[input_key]})
            state[output_key] = result
            return state
        return node

