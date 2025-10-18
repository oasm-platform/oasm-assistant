class NucleiGenerationPrompts:
    """Prompts for Nuclei template generation tasks"""

    @staticmethod
    def get_nuclei_template_generation_prompt(question: str, rag_context: str = "") -> str:
        """
        Get the Nuclei template generation prompt with RAG support

        Args:
            question: User's request for template generation
            rag_context: Retrieved similar templates from RAG (optional)

        Returns:
            Complete prompt for LLM
        """
        # Base prompt with user request
        base_prompt = f"""You are an expert security researcher specializing in creating Nuclei templates for vulnerability detection and security testing.

USER REQUEST:
{question}
"""

        # Add RAG examples section if context is available
        if rag_context and rag_context.strip():
            rag_section = f"""
REFERENCE TEMPLATES FROM DATABASE:
Below are high-quality Nuclei templates from our database that are similar to your request. These are REAL, PRODUCTION templates that you should learn from.

{rag_context}

CRITICAL INSTRUCTIONS FOR USING REFERENCES:
1. STUDY the reference templates above carefully - they show proven patterns and best practices
2. ANALYZE their structure: how they define IDs, matchers, extractors, and detection logic
3. LEARN from their syntax, naming conventions, and organization
4. ADAPT relevant patterns to create your template - DO NOT copy verbatim
5. If your request is similar to a reference, use it as inspiration but customize for the specific vulnerability
6. Pay attention to how references handle edge cases, false positives, and detection accuracy
7. Maintain the same level of quality and thoroughness as the references

"""
            base_prompt += rag_section

        # Add task description and requirements
        task_prompt = """
YOUR TASK:
Generate a complete, production-ready Nuclei template based on the user's request. The template should follow Nuclei's YAML syntax and best practices.

NUCLEI TEMPLATE STRUCTURE:
A Nuclei template typically includes:
1. id: Unique identifier (lowercase, hyphenated, descriptive)
2. info: Metadata section with:
   - name: Clear, descriptive name of the vulnerability/check
   - author: Template author (use your name or team)
   - severity: info/low/medium/high/critical (choose appropriately)
   - description: Detailed explanation of what this detects and why it matters
   - tags: Relevant tags for categorization (e.g., cve, exposure, misconfiguration)
   - reference: URLs to CVE details, advisories, or documentation (if applicable)
   - metadata: Additional context like CVE IDs, affected products, etc.
3. requests: HTTP/Network requests configuration with:
   - method: GET/POST/PUT/DELETE/PATCH etc.
   - path: Target paths/endpoints to test (use variables like {{BaseURL}})
   - headers: Custom headers if needed
   - body: Request body for POST/PUT (if applicable)
   - matchers-condition: and/or - how to combine matchers
   - matchers: Detection conditions (word, regex, status, dsl, binary)
   - extractors: Data extraction rules (optional, for gathering info)

BEST PRACTICES:
1. Create specific, accurate matchers to minimize false positives
2. Use multiple matcher types together (e.g., status + word) for reliability
3. Include multiple path variations to improve coverage
4. Add meaningful tags that help categorization and searching
5. Write clear descriptions that explain the security impact
6. Use regex matchers for flexible pattern matching when needed
7. Test for specific error messages or response patterns unique to the vulnerability
8. Consider different HTTP methods if the vulnerability can be triggered multiple ways
9. Use DSL matchers for complex logic (e.g., response time, size checks)
10. Include extractors to pull out useful information like versions, tokens, etc.

COMMON TEMPLATE PATTERNS:

For CVE/Vulnerability Detection:
```yaml
id: cve-YYYY-NNNNN-component

info:
  name: Component - Vulnerability Description
  author: researcher-name
  severity: critical/high/medium/low
  description: |
    Detailed description of the vulnerability, impact, and affected versions.
  reference:
    - https://nvd.nist.gov/vuln/detail/CVE-YYYY-NNNNN
    - https://vendor-advisory-url
  tags: cve,cve-yyyy,component-name,severity-level
  metadata:
    verified: true
    max-request: 2

requests:
  - method: GET
    path:
      - "{{{{BaseURL}}}}/vulnerable/path"
      - "{{{{BaseURL}}}}/alternative/path"

    matchers-condition: and
    matchers:
      - type: status
        status:
          - 200

      - type: word
        words:
          - "unique_error_identifier"
          - "version_indicator"
        condition: and

      - type: regex
        regex:
          - 'pattern_specific_to_vulnerability'
```

For Exposure/Misconfiguration Detection:
```yaml
id: exposed-resource-panel

info:
  name: Exposed Resource Panel
  author: researcher-name
  severity: medium
  description: |
    Detects publicly accessible administration/sensitive panel.
  tags: exposure,misconfig,panel

requests:
  - method: GET
    path:
      - "{{{{BaseURL}}}}/admin"
      - "{{{{BaseURL}}}}/dashboard"

    matchers-condition: or
    matchers:
      - type: word
        words:
          - "Login Panel"
          - "Administration"
        part: body

      - type: status
        status:
          - 200
```

REQUIREMENTS:
1. Generate ONLY the YAML template code, no additional explanations before or after
2. Use proper YAML syntax with correct indentation (2 spaces)
3. Include appropriate matchers based on the vulnerability type
4. Set realistic severity levels based on actual security impact
5. Add relevant, searchable tags
6. Use {{{{BaseURL}}}} for dynamic URL construction
7. Include multiple path variations when applicable
8. Use appropriate matcher types: word, regex, status, dsl, binary
9. Add clear descriptions that explain what the template detects and why it matters
10. Follow the patterns shown in reference templates (if provided)

OUTPUT FORMAT:
Return ONLY the complete YAML template code, properly formatted and ready to use with Nuclei.
Do not include markdown code blocks (no ```yaml or ```) or any explanations - just the raw YAML content starting with 'id:'.
"""

        return base_prompt + task_prompt
