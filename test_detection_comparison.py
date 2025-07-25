#!/usr/bin/env python3
"""Compare VS Code language detection with pattern-based detection."""

import asyncio
import logging

# Suppress debug logging
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('blib2to3').setLevel(logging.WARNING)
logging.getLogger('src.crawler').setLevel(logging.WARNING)

from src.crawler.vscode_language_detector import detect_language
from src.crawler.html_code_extractor import HTMLCodeExtractor

# Test snippets that might be tricky
TRICKY_CASES = [
    {
        "name": "React JSX",
        "code": """const Button = ({ onClick, children }) => {
  return (
    <button className="btn btn-primary" onClick={onClick}>
      {children}
    </button>
  );
};""",
        "expected": "javascript/jsx"
    },
    {
        "name": "Dockerfile",
        "code": """FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
EXPOSE 3000
CMD ["node", "server.js"]""",
        "expected": "dockerfile"
    },
    {
        "name": "YAML",
        "code": """version: '3.8'
services:
  web:
    build: .
    ports:
      - "3000:3000"
    environment:
      NODE_ENV: production
      DATABASE_URL: ${DATABASE_URL}""",
        "expected": "yaml"
    },
    {
        "name": "Makefile",
        "code": """.PHONY: build test clean

build:
\tgo build -o bin/app cmd/main.go

test:
\tgo test ./... -v

clean:
\trm -rf bin/""",
        "expected": "makefile"
    },
    {
        "name": "GraphQL",
        "code": """query GetUser($id: ID!) {
  user(id: $id) {
    id
    name
    email
    posts {
      title
      createdAt
    }
  }
}""",
        "expected": "graphql"
    },
    {
        "name": "Terraform",
        "code": """resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t2.micro"

  tags = {
    Name = "HelloWorld"
  }
}""",
        "expected": "hcl/terraform"
    }
]


async def test_comparison():
    """Compare VS Code detection with pattern-based detection."""
    extractor = HTMLCodeExtractor()
    
    print("VS Code Language Detection vs Pattern-Based Detection")
    print("=" * 70)
    print(f"{'Test Case':<20} {'VS Code':<20} {'Pattern':<20} {'Match':<10}")
    print("-" * 70)
    
    for case in TRICKY_CASES:
        # VS Code detection
        vs_result = await detect_language(case['code'])
        vs_lang = 'unknown'
        vs_conf = 0.0
        
        if vs_result.get('success') and vs_result.get('topResult'):
            vs_lang = vs_result['topResult']['language']
            vs_conf = vs_result['topResult']['confidence']
        
        # Pattern-based detection
        pattern_lang = extractor._pattern_based_detection(case['code'])
        
        # Check if they match
        match = "✅" if vs_lang == pattern_lang else "❌"
        
        print(f"{case['name']:<20} {vs_lang:<20} {pattern_lang:<20} {match:<10}")
        
        # Show confidence for VS Code
        if vs_conf > 0:
            print(f"{'':20} (conf: {vs_conf:.3f})")
        
        # Show top 3 VS Code results if available
        if vs_result.get('allResults') and len(vs_result['allResults']) > 1:
            print(f"{'':20} Other options: ", end="")
            other_results = vs_result['allResults'][1:3]
            options = [f"{r['language']} ({r['confidence']:.3f})" for r in other_results]
            print(", ".join(options))
        
        print()


async def main():
    await test_comparison()


if __name__ == "__main__":
    asyncio.run(main())