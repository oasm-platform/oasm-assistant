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
        # System role and user request
        base_prompt = f"""You are an expert Nuclei template developer with deep expertise in:
- Web application security testing and vulnerability detection
- Nuclei YAML template syntax and best practices
- Crafting precise matchers to minimize false positives/negatives
- Security standards (OWASP, CVE, CWE)

# USER REQUEST
{question}
"""

        # Add RAG examples section if context is available (THIS IS CRITICAL!)
        if rag_context and rag_context.strip():
            rag_section = f"""
# REFERENCE TEMPLATES (High-Quality Production Examples)
The following templates from our verified database are relevant to your request. Use them as authoritative examples of proper structure, syntax, and detection patterns.

{rag_context}

## How to Use These References:
1. **Analyze Structure**: Study the ID format, info section, request configuration, and matcher logic
2. **Learn Patterns**: Notice how matchers combine (status + word + regex) for accuracy
3. **Adopt Best Practices**: Use similar tag conventions, severity assessment, and documentation style
4. **Adapt, Don't Copy**: Customize the patterns for your specific use case - DO NOT copy verbatim
5. **Maintain Quality**: Match or exceed the thoroughness and precision of these references

---

"""
            base_prompt += rag_section

        # Add task description and requirements
        task_prompt = """
# YOUR TASK
Generate a **complete, production-ready Nuclei template** that follows official syntax and security best practices.

# NUCLEI TEMPLATE ANATOMY

## Required Components:

### 1. ID Field
```yaml
id: descriptive-component-vuln-name
```
- Lowercase with hyphens
- Format: `[type]-[component]-[description]` or `cve-YYYY-NNNNN-component`
- Examples: `apache-struts-rce`, `cve-2021-44228-log4j`

### 2. Info Section
```yaml
info:
  name: "Clear Vulnerability/Check Name"
  author: security-team
  severity: critical|high|medium|low|info
  description: |
    Comprehensive explanation of:
    - What vulnerability/issue is detected
    - Security impact and risk
    - Affected versions/components
  reference:
    - https://nvd.nist.gov/vuln/detail/CVE-YYYY-NNNNN
    - https://vendor-advisory.com
  tags: cve,cve-yyyy,product,category
  metadata:
    verified: true
    max-request: 1
```

### 3. Requests Section
```yaml
requests:
  - method: GET
    path:
      - "{{{{BaseURL}}}}/path/to/test"
      - "{{{{BaseURL}}}}/alternative/path"

    headers:
      User-Agent: "Custom-Agent"

    matchers-condition: and  # or 'or'
    matchers:
      - type: status
        status: [200, 201]

      - type: word
        words:
          - "error_signature"
          - "vulnerable_version"
        condition: and
        part: body

      - type: regex
        regex:
          - 'vulnerability_pattern_\\d+'
        part: body
```

# QUALITY GUIDELINES

## Matcher Best Practices:
✅ **DO:**
- Combine multiple matcher types (status + word + regex) for high accuracy
- Use specific, unique error signatures to avoid false positives
- Include multiple path variations for better coverage
- Set `matchers-condition: and` for stricter matching (preferred)
- Test status codes, response bodies, AND headers when applicable
- Use `part: body|header|all` to specify where to match

❌ **DON'T:**
- Rely on single generic matchers (e.g., only status 200)
- Use overly broad regex patterns that match unrelated content
- Forget to specify matcher conditions when using multiple matchers
- Create templates without understanding the vulnerability being detected

## Severity Assessment:
- **Critical**: RCE, authentication bypass, direct data exposure
- **High**: SQL injection, XSS (stored), privilege escalation
- **Medium**: CSRF, XSS (reflected), information disclosure
- **Low**: Minor misconfigurations, verbose errors
- **Info**: Version detection, non-security checks

# TEMPLATE PATTERNS BY TYPE

## Pattern 1: CVE Vulnerability Detection
```yaml
id: cve-YYYY-NNNNN-component

info:
  name: Component Version - Specific Vulnerability Name
  author: security-team
  severity: critical
  description: |
    Detects CVE-YYYY-NNNNN in ComponentName affecting versions X.X to Y.Y.
    This vulnerability allows [attack vector] leading to [impact].
    Successful exploitation can result in [consequences].
  reference:
    - https://nvd.nist.gov/vuln/detail/CVE-YYYY-NNNNN
    - https://vendor-advisory.com/CVE-YYYY-NNNNN
  tags: cve,cve-yyyy,component,rce
  classification:
    cvss-metrics: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
    cvss-score: 9.8
    cve-id: CVE-YYYY-NNNNN
  metadata:
    verified: true
    max-request: 2

requests:
  - method: GET
    path:
      - "{{{{BaseURL}}}}/vulnerable/endpoint"
      - "{{{{BaseURL}}}}/api/vulnerable/path"

    matchers-condition: and
    matchers:
      - type: status
        status: [200, 500]

      - type: word
        words:
          - "unique_error_string"
          - "stack_trace_indicator"
        condition: or
        part: body

      - type: regex
        regex:
          - 'ComponentName[/\\s]+(v)?[0-9]+\\.[0-9]+\\.[0-9]+'
        part: body
```

## Pattern 2: Exposed Panel/Resource Detection
```yaml
id: exposed-admin-panel

info:
  name: Exposed Administration Panel
  author: security-team
  severity: medium
  description: |
    Detects publicly accessible administration panels that should be protected.
    Exposure increases attack surface and may lead to unauthorized access attempts.
  tags: exposure,panel,misconfig
  metadata:
    max-request: 3

requests:
  - method: GET
    path:
      - "{{{{BaseURL}}}}/admin"
      - "{{{{BaseURL}}}}/admin/login"
      - "{{{{BaseURL}}}}/administrator"

    matchers-condition: and
    matchers:
      - type: status
        status: [200]

      - type: word
        words:
          - "Admin Login"
          - "Administration Panel"
          - "Dashboard Login"
        condition: or
        part: body
        case-insensitive: true
```

## Pattern 3: Configuration/Disclosure Issue
```yaml
id: service-info-disclosure

info:
  name: Service Information Disclosure
  author: security-team
  severity: low
  description: |
    Detects verbose error messages or debug information leaking sensitive details
    about the application's configuration, versions, or internal structure.
  tags: exposure,info-disclosure,config
  metadata:
    max-request: 1

requests:
  - method: GET
    path:
      - "{{{{BaseURL}}}}/debug"
      - "{{{{BaseURL}}}}/actuator/env"

    matchers:
      - type: word
        words:
          - "Database Connection"
          - "API Key"
          - "Secret"
        condition: or
        part: body
        case-insensitive: true

      - type: status
        status: [200]
```

# CRITICAL OUTPUT REQUIREMENTS

⚠️ **IMPORTANT**: Your response must contain ONLY the YAML template code.

**Format Rules:**
1. ✅ Start directly with `id:` (no explanation before)
2. ✅ Use 2-space indentation (not tabs)
3. ✅ End with the last line of YAML (no explanation after)
4. ❌ NO markdown code blocks (no ```yaml or ```)
5. ❌ NO explanatory text or comments outside the YAML
6. ✅ Use `{{{{BaseURL}}}}` with 4 curly braces for URL variables
7. ✅ Follow exact YAML syntax from reference templates (if provided)

**Quality Checklist:**
- [ ] ID is descriptive and follows naming convention
- [ ] Severity matches the actual security impact
- [ ] Description explains what, why, and impact
- [ ] Matchers are specific enough to avoid false positives
- [ ] Multiple matcher types used together (status + word/regex)
- [ ] Tags are relevant and searchable
- [ ] References included (for CVEs)
- [ ] Paths include common variations
"""

        return base_prompt + task_prompt
