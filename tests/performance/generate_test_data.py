"""Generate realistic test data for LLM concurrency performance testing."""

import json
import random
from pathlib import Path
from typing import Any

# Code templates for different languages
CODE_TEMPLATES = {
    "javascript": [
        """function {func_name}({params}) {{
    // {comment}
    const {var_name} = {value};
    {body}
    return {return_value};
}}""",
        """const {func_name} = ({params}) => {{
    // {comment}
    {body}
    return {return_value};
}};""",
        """import {{ {imports} }} from '{module}';

export const {func_name} = async ({params}) => {{
    try {{
        const result = await {async_call}();
        {body}
        return result;
    }} catch (error) {{
        console.error('Error:', error);
        throw error;
    }}
}};""",
        """class {class_name} {{
    constructor({params}) {{
        {init_body}
    }}
    
    {method_name}({method_params}) {{
        {method_body}
    }}
}}"""
    ],

    "typescript": [
        """interface {interface_name} {{
    {properties}
}}

function {func_name}({params}): {return_type} {{
    // {comment}
    const {var_name}: {type} = {value};
    {body}
    return {return_value};
}}""",
        """type {type_name} = {{
    {properties}
}};

export const {func_name} = async ({params}): Promise<{return_type}> => {{
    {body}
    return {return_value};
}};""",
        """export class {class_name} implements {interface_name} {{
    private {property}: {type};
    
    constructor({params}) {{
        {init_body}
    }}
    
    public {method_name}({method_params}): {return_type} {{
        {method_body}
    }}
}}"""
    ],

    "python": [
        """def {func_name}({params}):
    \"\"\"{docstring}\"\"\"
    {var_name} = {value}
    {body}
    return {return_value}""",
        """class {class_name}:
    \"\"\"{docstring}\"\"\"
    
    def __init__(self, {params}):
        {init_body}
    
    def {method_name}(self, {method_params}):
        {method_body}
        return {return_value}""",
        """import {module}
from {package} import {imports}

async def {func_name}({params}):
    \"\"\"{docstring}\"\"\"
    try:
        result = await {async_call}()
        {body}
        return result
    except Exception as e:
        logger.error(f"Error: {{e}}")
        raise""",
        """@dataclass
class {class_name}:
    {properties}
    
    def {method_name}(self) -> {return_type}:
        {method_body}"""
    ],

    "react": [
        """import React, {{ useState, useEffect }} from 'react';

export function {component_name}({{ {props} }}) {{
    const [{state_var}, set{state_var}] = useState({initial_value});
    
    useEffect(() => {{
        {effect_body}
    }}, [{dependencies}]);
    
    return (
        <div className="{class_name}">
            {jsx_content}
        </div>
    );
}}""",
        """import {{ {imports} }} from '{library}';

const {component_name} = ({{ {props} }}) => {{
    const {hook_result} = {hook_name}({hook_params});
    
    const handle{event_name} = ({event_params}) => {{
        {event_handler}
    }};
    
    return (
        <>
            {jsx_content}
        </>
    );
}};

export default {component_name};"""
    ]
}

# Variable names and values for template filling
VARIABLE_NAMES = ["data", "result", "value", "item", "user", "config", "response", "request", "state", "props"]
FUNCTION_NAMES = ["processData", "handleClick", "fetchUser", "validateInput", "transformResponse",
                  "calculateTotal", "renderComponent", "updateState", "parseConfig", "formatDate"]
CLASS_NAMES = ["UserService", "DataProcessor", "APIClient", "Component", "Controller", "Manager", "Handler"]
PARAM_NAMES = ["id", "name", "value", "options", "callback", "data", "config", "props", "state"]
RETURN_TYPES = ["string", "number", "boolean", "void", "any", "Promise<any>", "JSX.Element", "object"]
PROPERTIES = ["id: string", "name: string", "value: number", "enabled: boolean", "data: any[]",
              "config: Config", "status: Status", "createdAt: Date"]

# Comments and docstrings
COMMENTS = [
    "Process the input data",
    "Handle user interaction",
    "Fetch data from API",
    "Validate and transform input",
    "Update component state",
    "Calculate derived values",
    "Initialize configuration",
    "Clean up resources",
    "Format output for display",
    "Check permissions and access"
]

# Source URLs
SOURCE_URLS = [
    "https://nextjs.org/docs/getting-started",
    "https://nextjs.org/docs/api-routes",
    "https://reactjs.org/docs/hooks-intro.html",
    "https://docs.python.org/3/tutorial/",
    "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
    "https://www.typescriptlang.org/docs/",
    "https://nodejs.org/en/docs/",
    "https://expressjs.com/en/guide/",
    "https://docs.djangoproject.com/en/stable/",
    "https://flask.palletsprojects.com/en/latest/"
]


def generate_random_body(lines: int, language: str) -> str:
    """Generate random code body with specified number of lines."""
    body_lines = []

    for i in range(lines):
        indent = "    " if language == "python" else "        "

        # Generate different types of statements
        statement_type = random.choice(["assignment", "condition", "loop", "call", "comment"])

        if statement_type == "assignment":
            var = random.choice(VARIABLE_NAMES)
            value = random.choice(["true", "false", "null", "42", "'string'", "[]", "{}"])
            if language == "python":
                body_lines.append(f"{indent}{var} = {value}")
            else:
                body_lines.append(f"{indent}const {var} = {value};")

        elif statement_type == "condition":
            condition = random.choice(["value > 0", "data !== null", "isValid", "user.active"])
            if language == "python":
                body_lines.append(f"{indent}if {condition}:")
                body_lines.append(f"{indent}    pass")
            else:
                body_lines.append(f"{indent}if ({condition}) {{")
                body_lines.append(f"{indent}    // Do something")
                body_lines.append(f"{indent}}}")

        elif statement_type == "loop":
            if language == "python":
                body_lines.append(f"{indent}for item in items:")
                body_lines.append(f"{indent}    process(item)")
            else:
                body_lines.append(f"{indent}items.forEach(item => {{")
                body_lines.append(f"{indent}    process(item);")
                body_lines.append(f"{indent}}});")

        elif statement_type == "call":
            func = random.choice(FUNCTION_NAMES)
            if language == "python":
                body_lines.append(f"{indent}{func}()")
            else:
                body_lines.append(f"{indent}{func}();")

        elif statement_type == "comment":
            comment = random.choice(COMMENTS)
            if language == "python":
                body_lines.append(f"{indent}# {comment}")
            else:
                body_lines.append(f"{indent}// {comment}")

    return "\n".join(body_lines)


def fill_template(template: str, language: str, target_lines: int) -> str:
    """Fill a code template with random values."""
    # Calculate how many lines the template itself takes
    template_lines = template.count('\n') + 1
    body_lines = max(1, target_lines - template_lines - 5)  # Leave room for template

    replacements = {
        "func_name": random.choice(FUNCTION_NAMES),
        "class_name": random.choice(CLASS_NAMES),
        "component_name": random.choice(CLASS_NAMES),
        "interface_name": "I" + random.choice(CLASS_NAMES),
        "type_name": "T" + random.choice(CLASS_NAMES),
        "params": ", ".join(random.sample(PARAM_NAMES, random.randint(0, 3))),
        "method_params": ", ".join(random.sample(PARAM_NAMES, random.randint(0, 2))),
        "var_name": random.choice(VARIABLE_NAMES),
        "state_var": random.choice(VARIABLE_NAMES).capitalize(),
        "value": random.choice(["null", "0", "''", "[]", "{}", "true", "false"]),
        "return_value": random.choice(["result", "data", "true", "null", "{}"]),
        "return_type": random.choice(RETURN_TYPES),
        "type": random.choice(RETURN_TYPES),
        "property": random.choice(VARIABLE_NAMES),
        "properties": "\n    ".join(random.sample(PROPERTIES, random.randint(2, 5))),
        "comment": random.choice(COMMENTS),
        "docstring": random.choice(COMMENTS),
        "body": generate_random_body(body_lines, language),
        "init_body": generate_random_body(2, language),
        "method_body": generate_random_body(3, language),
        "effect_body": generate_random_body(2, language),
        "event_handler": generate_random_body(2, language),
        "method_name": random.choice(FUNCTION_NAMES),
        "module": random.choice(["lodash", "axios", "react", "express", "numpy", "pandas"]),
        "package": random.choice(["utils", "helpers", "services", "components"]),
        "imports": ", ".join(random.sample(FUNCTION_NAMES, random.randint(1, 3))),
        "library": random.choice(["@mui/material", "antd", "react-router-dom"]),
        "props": ", ".join(random.sample(PARAM_NAMES, random.randint(1, 3))),
        "hook_name": random.choice(["useState", "useEffect", "useMemo", "useCallback"]),
        "hook_params": ", ".join(random.sample(PARAM_NAMES, random.randint(0, 2))),
        "hook_result": random.choice(VARIABLE_NAMES),
        "event_name": random.choice(["Click", "Submit", "Change", "Load"]),
        "event_params": "event",
        "dependencies": ", ".join(random.sample(VARIABLE_NAMES, random.randint(0, 2))),
        "class_name": random.choice(["container", "wrapper", "content", "header"]),
        "jsx_content": "<h1>Hello World</h1>\n            <p>Content goes here</p>",
        "async_call": random.choice(["fetchData", "apiRequest", "loadUser"]),
        "initial_value": random.choice(["null", "0", "''", "[]", "{}"])
    }

    # Replace all placeholders
    result = template
    for key, value in replacements.items():
        result = result.replace(f"{{{key}}}", str(value))

    return result


def generate_code_snippet(
    min_lines: int = 10,
    max_lines: int = 200,
    languages: list[str] = None
) -> dict[str, Any]:
    """Generate a single code snippet with metadata."""
    if languages is None:
        languages = list(CODE_TEMPLATES.keys())

    language = random.choice(languages)
    target_lines = random.randint(min_lines, max_lines)

    # Choose appropriate template based on target lines
    templates = CODE_TEMPLATES.get(language, CODE_TEMPLATES["javascript"])

    # For React, use the language as javascript/typescript
    if language == "react":
        actual_language = random.choice(["javascript", "typescript"])
    else:
        actual_language = language

    template = random.choice(templates)
    code = fill_template(template, actual_language, target_lines)

    # Create snippet metadata
    return {
        "content": code,
        "language": actual_language,
        "lines_of_code": code.count("\n") + 1,
        "source_url": random.choice(SOURCE_URLS),
        "context_before": f"// Previous section explains {random.choice(COMMENTS).lower()}",
        "context_after": f"// Next section covers {random.choice(COMMENTS).lower()}",
    }


def generate_test_dataset(
    num_snippets: int = 1000,
    output_file: str = "test_snippets.json"
) -> None:
    """Generate a complete test dataset."""
    print(f"Generating {num_snippets} test code snippets...")

    snippets = []

    # Distribution of languages
    language_distribution = {
        "javascript": 0.35,
        "typescript": 0.25,
        "python": 0.20,
        "react": 0.20
    }

    # Generate snippets according to distribution
    for language, ratio in language_distribution.items():
        count = int(num_snippets * ratio)
        print(f"  Generating {count} {language} snippets...")

        for i in range(count):
            # Vary the line counts
            if i % 10 == 0:  # 10% very small
                min_lines, max_lines = 5, 15
            elif i % 5 == 0:  # 20% large
                min_lines, max_lines = 100, 200
            else:  # 70% medium
                min_lines, max_lines = 20, 80

            snippet = generate_code_snippet(
                min_lines=min_lines,
                max_lines=max_lines,
                languages=[language]
            )
            snippets.append(snippet)

    # Shuffle snippets
    random.shuffle(snippets)

    # Save to file
    output_path = Path(__file__).parent / output_file
    with open(output_path, 'w') as f:
        json.dump({
            "metadata": {
                "total_snippets": len(snippets),
                "languages": list(language_distribution.keys()),
                "generated_at": "2024-01-10T10:00:00Z"
            },
            "snippets": snippets
        }, f, indent=2)

    print(f"✓ Generated {len(snippets)} snippets saved to {output_path}")

    # Print statistics
    print("\nDataset Statistics:")
    lang_counts = {}
    size_distribution = {"small": 0, "medium": 0, "large": 0}

    for snippet in snippets:
        lang = snippet["language"]
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

        lines = snippet["lines_of_code"]
        if lines < 20:
            size_distribution["small"] += 1
        elif lines < 100:
            size_distribution["medium"] += 1
        else:
            size_distribution["large"] += 1

    print("\nLanguage distribution:")
    for lang, count in sorted(lang_counts.items()):
        print(f"  {lang}: {count} ({count/len(snippets)*100:.1f}%)")

    print("\nSize distribution:")
    for size, count in size_distribution.items():
        print(f"  {size}: {count} ({count/len(snippets)*100:.1f}%)")


if __name__ == "__main__":
    generate_test_dataset(num_snippets=1000)
