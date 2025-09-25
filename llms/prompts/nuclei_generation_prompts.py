"""
Nuclei template generation prompts for OASM Assistant
"""


class NucleiGenerationPrompts:
    """Nuclei template generation prompt templates"""

    @staticmethod
    def get_nuclei_template_generation_prompt() -> str:
        """Main nuclei template generation prompt"""
        return """You are a Nuclei template generation specialist. Generate high-quality YAML templates for vulnerability detection.

## Template Structure Requirements:

```yaml
id: unique-template-id
info:
  name: "Template Name"
  author: oasm-assistant
  severity: low|medium|high|critical
  description: "Detailed description"
  classification:
    cvss-metrics: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N"
    cvss-score: 0.0
    cve-id: CVE-YYYY-NNNN (if applicable)
  metadata:
    verified: true
    shodan-query: "query if applicable"
  tags: tag1,tag2,tag3

http:
  - method: GET|POST
    path:
      - "{{BaseURL}}/path"
    headers:
      Header-Name: "value"
    body: |
      request body if needed
    matchers-condition: and|or
    matchers:
      - type: word|regex|status|size
        part: body|header|status
        words:
          - "detection string"
        condition: and|or
    extractors:
      - type: regex|xpath
        part: body|header
        regex:
          - 'pattern'
```

## Generation Guidelines:

1. **Template ID**: Use descriptive, unique identifiers
2. **Info Section**: Complete metadata with proper severity and classification
3. **Detection Logic**: Robust matchers to minimize false positives
4. **Performance**: Optimize for speed and accuracy
5. **Documentation**: Clear descriptions and usage notes

## Vulnerability Categories:
- Web application vulnerabilities (XSS, SQLi, etc.)
- Misconfigurations and exposures
- Information disclosure
- Authentication bypasses
- File inclusion vulnerabilities
- Server-side vulnerabilities

## Template Quality Checklist:
✓ Unique and descriptive ID
✓ Complete info section with metadata
✓ Appropriate severity classification
✓ Robust detection logic
✓ Minimized false positives
✓ Performance optimized
✓ Proper YAML syntax
✓ Community standards compliance

Generate templates that are production-ready and follow Nuclei community best practices."""

    @staticmethod
    def get_cve_template_prompt(cve_id: str, description: str = "") -> str:
        """Generate template for specific CVE"""
        return f"""Generate a Nuclei template for {cve_id}.

CVE Details: {description}

Requirements:
1. Use CVE ID as base for template ID
2. Include CVE metadata in info section
3. Implement accurate detection logic
4. Set appropriate severity level
5. Add relevant tags and classification
6. Include CVSS scoring if available
7. Minimize false positives
8. Follow Nuclei template standards

Focus on creating a reliable detection method that accurately identifies the vulnerability without generating false positives."""

    @staticmethod
    def get_vulnerability_type_prompt(vuln_type: str) -> str:
        """Generate template for vulnerability type"""
        vuln_prompts = {
            "xss": "Generate a Nuclei template for Cross-Site Scripting (XSS) detection. Include both reflected and stored XSS patterns.",
            "sqli": "Generate a Nuclei template for SQL Injection detection. Cover various injection points and database types.",
            "lfi": "Generate a Nuclei template for Local File Inclusion (LFI) vulnerability detection.",
            "rfi": "Generate a Nuclei template for Remote File Inclusion (RFI) vulnerability detection.",
            "ssrf": "Generate a Nuclei template for Server-Side Request Forgery (SSRF) detection.",
            "csrf": "Generate a Nuclei template for Cross-Site Request Forgery (CSRF) vulnerability detection.",
            "rce": "Generate a Nuclei template for Remote Code Execution (RCE) vulnerability detection.",
            "path_traversal": "Generate a Nuclei template for Path Traversal vulnerability detection.",
            "open_redirect": "Generate a Nuclei template for Open Redirect vulnerability detection.",
            "xxe": "Generate a Nuclei template for XML External Entity (XXE) vulnerability detection."
        }

        specific_prompt = vuln_prompts.get(vuln_type.lower(), f"Generate a Nuclei template for {vuln_type} vulnerability detection.")

        return f"""{specific_prompt}

Template Requirements:
- Accurate detection patterns
- Multiple test vectors
- Proper severity classification
- Comprehensive info section
- Optimized for performance
- Minimal false positives
- Industry standard compliance

Include various attack vectors and payloads commonly associated with {vuln_type} vulnerabilities."""

    @staticmethod
    def get_technology_template_prompt(technology: str) -> str:
        """Generate template for specific technology"""
        return f"""Generate a Nuclei template for detecting {technology} vulnerabilities or misconfigurations.

Focus Areas:
1. Version detection and vulnerability mapping
2. Default configurations and credentials
3. Known security issues and exposures
4. Misconfiguration detection
5. Information disclosure vulnerabilities

Template should:
- Identify {technology} installations
- Check for known vulnerabilities
- Detect common misconfigurations
- Include version-specific tests
- Provide actionable results
- Follow security best practices

Generate comprehensive coverage for {technology} security assessment."""

    @staticmethod
    def get_template_validation_prompt() -> str:
        """Validate generated nuclei template"""
        return """Validate this Nuclei template for quality and accuracy:

Validation Criteria:
1. **YAML Syntax**: Correct YAML structure and indentation
2. **Template Structure**: All required sections present
3. **Info Section**: Complete metadata with proper classification
4. **Detection Logic**: Robust matchers and extractors
5. **Performance**: Optimized for speed and resource usage
6. **Accuracy**: Minimal false positive potential
7. **Security**: No sensitive information exposed
8. **Standards**: Nuclei community guidelines compliance

Provide:
- Validation results (pass/fail for each criteria)
- Identified issues and recommendations
- Optimization suggestions
- Security considerations
- Compliance assessment

Rate overall quality: Poor/Fair/Good/Excellent"""

    @staticmethod
    def get_template_enhancement_prompt() -> str:
        """Enhance existing nuclei template"""
        return """Enhance this Nuclei template to improve its effectiveness:

Enhancement Areas:
1. **Detection Accuracy**: Improve matchers and reduce false positives
2. **Coverage**: Add additional test vectors and edge cases
3. **Performance**: Optimize for speed and resource efficiency
4. **Metadata**: Enhance info section with better classification
5. **Documentation**: Improve descriptions and usage notes
6. **Standards**: Align with latest Nuclei best practices

Enhancement Guidelines:
- Maintain backward compatibility
- Preserve original functionality
- Add value without complexity
- Follow community standards
- Document all changes
- Test thoroughly

Provide enhanced template with detailed changelog."""

    @staticmethod
    def get_bulk_template_generation_prompt(target_list: list) -> str:
        """Generate multiple templates for a list of targets"""
        targets = ", ".join(target_list)

        return f"""Generate Nuclei templates for the following targets: {targets}

Bulk Generation Requirements:
1. Create individual templates for each target
2. Ensure unique template IDs
3. Maintain consistent quality standards
4. Optimize for batch scanning
5. Include cross-reference metadata
6. Follow naming conventions

For each template provide:
- Unique identifier
- Comprehensive info section
- Targeted detection logic
- Appropriate severity classification
- Relevant tags and metadata
- Performance optimization

Generate a complete template set suitable for production use."""