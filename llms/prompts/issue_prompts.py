from typing import Dict, Any, Optional
import json

class IssuePrompts:
    """Optimized prompt templates for @cai - Security Expert AI"""
    
    # Condensed system prompt
    SYSTEM_PROMPT = """You are @cai, a cybersecurity expert in infrastructure security, web hardening, and vulnerability remediation.

Response requirements: Actionable solutions with implementation steps, security implications, verification methods, and best practices (OWASP, CIS, NIST). Use code blocks."""

    # Base response structure (reusable)
    BASE_STRUCTURE = """
## Response Structure:
1. **Analysis**: Root cause, impact, affected components
2. **Solution**: Step-by-step fix with code examples
3. **Verification**: Testing commands and expected results
4. **Prevention**: Best practices and monitoring"""

    @staticmethod
    def _format_metadata(metadata: Optional[Dict[str, Any]]) -> str:
        """Format metadata compactly"""
        if not metadata:
            return ""
        
        parts = ["\n## Context:"]
        for key, value in metadata.items():
            if isinstance(value, (dict, list)):
                parts.append(f"**{key}**: {json.dumps(value, separators=(',', ':'))}")
            else:
                parts.append(f"**{key}**: {value}")
        
        return "\n".join(parts)

    @staticmethod
    def get_ssl_issue_prompt(question: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Prompt for SSL/TLS issues"""
        ctx = IssuePrompts._format_metadata(metadata)
        
        return f"""{IssuePrompts.SYSTEM_PROMPT}

**Specialization**: SSL/TLS (Nginx, Apache, HAProxy, Let's Encrypt, OpenSSL, TLS 1.2/1.3, cipher suites, HSTS, OCSP)

**Question**: {question}
{ctx}
{IssuePrompts.BASE_STRUCTURE}

Additional for SSL:
- Include SSL Labs validation steps
- Provide cipher suite recommendations

Begin:"""

    @staticmethod
    def get_vulnerability_issue_prompt(question: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Prompt for security vulnerabilities"""
        ctx = IssuePrompts._format_metadata(metadata)
        
        return f"""{IssuePrompts.SYSTEM_PROMPT}

**Specialization**: Vulnerability Assessment (OWASP Top 10, CVE, patch management, pentesting, secure coding)

**Question**: {question}
{ctx}

## Response Structure:
1. **Assessment**: CVE/CWE ID, Severity (CVSS), Attack Vector, Impact
2. **Remediation**:
   - Immediate: Emergency mitigations (24h)
   - Permanent: Patches, code fixes, hardening (with code)
3. **Verification**: Testing procedures, regression checks
4. **Long-term**: Hardening, monitoring, policy updates
5. **References**: CVE links, vendor advisories

Begin:"""

    @staticmethod
    def get_general_security_prompt(question: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Prompt for general security questions"""
        ctx = IssuePrompts._format_metadata(metadata)
        
        return f"""{IssuePrompts.SYSTEM_PROMPT}

**Specialization**: General Security (firewall, access control, auth, encryption, architecture, incident response, compliance)

**Question**: {question}
{ctx}
{IssuePrompts.BASE_STRUCTURE}

Additional considerations:
- Compliance (PCI-DSS, HIPAA, GDPR)
- Performance and maintenance trade-offs

Begin:"""

    @staticmethod
    def get_prompt_by_category(
        category: str, 
        question: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get appropriate prompt based on issue category
        
        Args:
            category: 'ssl', 'vulnerability', or 'general'
            question: User's security question
            metadata: Additional system context
            
        Returns:
            Formatted prompt string
        """
        prompts = {
            'ssl': IssuePrompts.get_ssl_issue_prompt,
            'vulnerability': IssuePrompts.get_vulnerability_issue_prompt,
            'general': IssuePrompts.get_general_security_prompt
        }
        
        prompt_func = prompts.get(category.lower(), IssuePrompts.get_general_security_prompt)
        return prompt_func(question, metadata)

