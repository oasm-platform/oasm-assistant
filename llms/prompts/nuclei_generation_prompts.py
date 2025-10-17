class NucleiGenerationPrompts:
    """Prompts for Nuclei template generation tasks"""

    @staticmethod
    def get_nuclei_template_generation_prompt(question: str) -> str:
        """Get the Nuclei template generation prompt"""
        prompt = f"""
You are an expert security researcher specializing in creating Nuclei templates for vulnerability detection and security testing.

USER REQUEST:
{question}

YOUR TASK:
Generate a complete, production-ready Nuclei template based on the user's request. The template should follow Nuclei's YAML syntax and best practices.

NUCLEI TEMPLATE STRUCTURE:
A Nuclei template typically includes:
1. id: Unique identifier for the template
2. info: Metadata section with:
   - name: Descriptive name of the vulnerability/check
   - author: Template author
   - severity: info/low/medium/high/critical
   - description: Detailed description
   - tags: Relevant tags for categorization
   - reference: URLs to vulnerability details (if applicable)
3. requests: HTTP requests configuration with:
   - method: GET/POST/PUT/DELETE etc.
   - path: Target paths to test
   - matchers: Conditions to identify successful detection
   - extractors: Data extraction rules (optional)

EXAMPLE TEMPLATE FORMAT:
```yaml
id: example-vulnerability

info:
  name: Example Vulnerability Detection
  author: security-researcher
  severity: medium
  description: Detects example vulnerability in web applications
  tags: example,vulnerability,security
  reference:
    - https://example.com/vulnerability-details

requests:
  - method: GET
    path:
      - "{{{{BaseURL}}}}/vulnerable-endpoint"
      - "{{{{BaseURL}}}}/admin/config"

    matchers-condition: and
    matchers:
      - type: word
        words:
          - "sensitive_data"
          - "error_message"
        part: body

      - type: status
        status:
          - 200
```

REQUIREMENTS:
1. Generate ONLY the YAML template code, no additional explanations
2. Use proper YAML syntax and indentation
3. Include appropriate matchers based on the vulnerability type
4. Set realistic severity levels
5. Add relevant tags for easy searching
6. Use {{{{BaseURL}}}} for dynamic URL construction
7. Include multiple path variations when applicable
8. Use appropriate matcher types: word, regex, status, dsl
9. Add descriptions that clearly explain what the template detects

OUTPUT FORMAT:
Return ONLY the complete YAML template code, properly formatted and ready to use with Nuclei.
Do not include any markdown code blocks or explanations - just the raw YAML content.
"""
        return prompt
