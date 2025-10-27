"""
Generate Security Playbooks as PDF for Knowledge Base
Includes OWASP Top 10, CWE Top 25, Common Attack Patterns, Remediation Guides
"""
import os
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

from common.logger import logger


class SecurityPlaybookGenerator:
    """Generate comprehensive security playbooks as PDF"""

    def __init__(self, output_dir: str = "knowledge/playbooks"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=12
        ))

        self.styles.add(ParagraphStyle(
            name='Code',
            parent=self.styles['Code'],
            fontSize=9,
            fontName='Courier',
            textColor=colors.HexColor('#d73a49'),
            backColor=colors.HexColor('#f6f8fa'),
            leftIndent=20,
            rightIndent=20
        ))

    def generate_all_playbooks(self):
        """Generate all security playbooks"""
        logger.info("Generating security playbooks...")

        self.generate_owasp_top10_playbook()
        self.generate_cwe_top25_playbook()
        self.generate_remediation_playbook()
        self.generate_incident_response_playbook()

        logger.info(f"All playbooks generated in: {self.output_dir}")

    # ==========================================================================
    # OWASP TOP 10 PLAYBOOK
    # ==========================================================================

    def generate_owasp_top10_playbook(self):
        """Generate OWASP Top 10 2021 Playbook"""
        logger.info("Generating OWASP Top 10 playbook...")

        filename = self.output_dir / "OWASP_Top10_2021_Playbook.pdf"
        doc = SimpleDocTemplate(str(filename), pagesize=letter)
        story = []

        # Title
        story.append(Paragraph("OWASP Top 10 2021", self.styles['CustomTitle']))
        story.append(Paragraph("Security Vulnerabilities Playbook", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.5*inch))

        # Metadata
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d')}", self.styles['Normal']))
        story.append(Paragraph("Version: 2021", self.styles['Normal']))
        story.append(PageBreak())

        # Table of Contents
        story.append(Paragraph("Table of Contents", self.styles['Heading1']))
        toc_data = [
            ["A01:2021", "Broken Access Control"],
            ["A02:2021", "Cryptographic Failures"],
            ["A03:2021", "Injection"],
            ["A04:2021", "Insecure Design"],
            ["A05:2021", "Security Misconfiguration"],
            ["A06:2021", "Vulnerable and Outdated Components"],
            ["A07:2021", "Identification and Authentication Failures"],
            ["A08:2021", "Software and Data Integrity Failures"],
            ["A09:2021", "Security Logging and Monitoring Failures"],
            ["A10:2021", "Server-Side Request Forgery (SSRF)"],
        ]
        toc_table = Table(toc_data, colWidths=[1.5*inch, 4.5*inch])
        toc_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(toc_table)
        story.append(PageBreak())

        # A01:2021 - Broken Access Control
        story.extend(self._create_owasp_section(
            category="A01:2021",
            title="Broken Access Control",
            risk_level="HIGH",
            description="""
Access control enforces policy such that users cannot act outside of their intended permissions.
Failures typically lead to unauthorized information disclosure, modification, or destruction of all data
or performing a business function outside the user's limits.
            """,
            common_weaknesses=[
                "CWE-22: Path Traversal",
                "CWE-23: Relative Path Traversal",
                "CWE-35: Path Traversal: '.../...//'",
                "CWE-59: Improper Link Resolution Before File Access",
                "CWE-200: Exposure of Sensitive Information",
                "CWE-201: Insertion of Sensitive Information Into Sent Data",
                "CWE-219: Storage of File with Sensitive Data Under Web Root",
                "CWE-264: Permissions, Privileges, and Access Controls",
                "CWE-275: Permission Issues",
                "CWE-284: Improper Access Control",
                "CWE-285: Improper Authorization",
                "CWE-352: Cross-Site Request Forgery (CSRF)",
                "CWE-359: Exposure of Private Personal Information to an Unauthorized Actor",
                "CWE-377: Insecure Temporary File",
                "CWE-402: Transmission of Private Resources into a New Sphere",
                "CWE-425: Direct Request ('Forced Browsing')",
                "CWE-441: Unintended Proxy or Intermediary",
                "CWE-497: Exposure of Sensitive System Information",
                "CWE-538: Insertion of Sensitive Information into Externally-Accessible File",
                "CWE-540: Inclusion of Sensitive Information in Source Code",
                "CWE-548: Exposure of Information Through Directory Listing",
                "CWE-552: Files or Directories Accessible to External Parties",
                "CWE-566: Authorization Bypass Through User-Controlled SQL Primary Key",
                "CWE-601: URL Redirection to Untrusted Site ('Open Redirect')",
                "CWE-639: Authorization Bypass Through User-Controlled Key",
                "CWE-651: Exposure of WSDL File Containing Sensitive Information",
                "CWE-668: Exposure of Resource to Wrong Sphere",
                "CWE-706: Use of Incorrectly-Resolved Name or Reference",
                "CWE-862: Missing Authorization",
                "CWE-863: Incorrect Authorization",
                "CWE-913: Improper Control of Dynamically-Managed Code Resources",
                "CWE-922: Insecure Storage of Sensitive Information",
                "CWE-1275: Sensitive Cookie with Improper SameSite Attribute"
            ],
            attack_examples=[
                {
                    "name": "Path Traversal Attack",
                    "code": """
# Vulnerable code
file_path = request.GET.get('file')
with open(file_path, 'r') as f:
    content = f.read()

# Attack: ?file=../../etc/passwd
                    """
                },
                {
                    "name": "Insecure Direct Object Reference (IDOR)",
                    "code": """
# Vulnerable code
user_id = request.GET.get('user_id')
user_data = db.get_user(user_id)  # No authorization check!

# Attack: ?user_id=123 (access other user's data)
                    """
                },
                {
                    "name": "Missing Function Level Access Control",
                    "code": """
# Vulnerable code
@app.route('/admin/delete_user')
def delete_user():
    user_id = request.args.get('id')
    db.delete_user(user_id)  # No role check!

# Attack: Regular user can access /admin/delete_user
                    """
                }
            ],
            remediation={
                "immediate": [
                    "Implement deny by default access control",
                    "Disable directory listing on web servers",
                    "Log access control failures and alert admins",
                    "Rate limit API and controller access to minimize harm from automated attacks"
                ],
                "short_term": [
                    "Implement proper authorization checks at the application layer",
                    "Enforce record ownership checks",
                    "Use indirect object references (maps) instead of direct database IDs",
                    "Implement CSRF tokens for state-changing operations"
                ],
                "long_term": [
                    "Design and implement role-based access control (RBAC) or attribute-based access control (ABAC)",
                    "Implement centralized access control mechanism",
                    "Use automated testing to verify access controls",
                    "Model access controls to ensure they enforce business logic"
                ]
            },
            secure_code_examples=[
                {
                    "language": "Python (Flask)",
                    "code": """
# Secure implementation with authorization
from flask import abort
from functools import wraps

def require_ownership(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        resource_id = kwargs.get('resource_id')
        resource = db.get_resource(resource_id)

        # Check ownership
        if resource.owner_id != current_user.id:
            abort(403)  # Forbidden

        return f(*args, **kwargs)
    return decorated_function

@app.route('/resource/<int:resource_id>')
@login_required
@require_ownership
def get_resource(resource_id):
    resource = db.get_resource(resource_id)
    return jsonify(resource.to_dict())
                    """
                },
                {
                    "language": "Python (Django)",
                    "code": """
# Secure file access with whitelist
import os
from django.conf import settings

ALLOWED_FILES = {
    'report1': 'reports/monthly_report.pdf',
    'report2': 'reports/annual_report.pdf'
}

def get_file(request):
    file_key = request.GET.get('file')

    # Use whitelist mapping
    if file_key not in ALLOWED_FILES:
        return HttpResponseForbidden()

    file_path = os.path.join(settings.MEDIA_ROOT, ALLOWED_FILES[file_key])

    # Additional security: ensure path is within allowed directory
    if not os.path.realpath(file_path).startswith(settings.MEDIA_ROOT):
        return HttpResponseForbidden()

    return FileResponse(open(file_path, 'rb'))
                    """
                },
                {
                    "language": "JavaScript (Node.js/Express)",
                    "code": """
// Secure RBAC implementation
const requireRole = (allowedRoles) => {
  return (req, res, next) => {
    if (!req.user) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    if (!allowedRoles.includes(req.user.role)) {
      return res.status(403).json({ error: 'Forbidden' });
    }

    next();
  };
};

// Usage
app.delete('/api/users/:id',
  authenticate,
  requireRole(['admin']),
  async (req, res) => {
    const userId = req.params.id;
    await User.deleteById(userId);
    res.json({ success: true });
  }
);
                    """
                }
            ],
            testing_checklist=[
                "Test for horizontal privilege escalation (access other users' resources)",
                "Test for vertical privilege escalation (regular user accessing admin functions)",
                "Test path traversal in file operations",
                "Test direct object references (manipulate IDs in URLs)",
                "Verify CSRF protection on state-changing operations",
                "Test missing function level access control",
                "Test for metadata manipulation (JWT/Cookie tampering)",
                "Verify access control on APIs and services",
                "Test for CORS misconfiguration"
            ]
        ))

        # A03:2021 - Injection
        story.extend(self._create_owasp_section(
            category="A03:2021",
            title="Injection",
            risk_level="CRITICAL",
            description="""
An application is vulnerable to attack when user-supplied data is not validated, filtered, or sanitized.
Hostile data is directly used or concatenated in dynamic queries, commands, or stored procedures.
Most common injection types: SQL, NoSQL, OS command, LDAP, Expression Language (EL), OGNL injection.
            """,
            common_weaknesses=[
                "CWE-20: Improper Input Validation",
                "CWE-74: Improper Neutralization of Special Elements in Output",
                "CWE-75: Failure to Sanitize Special Elements into a Different Plane",
                "CWE-77: Improper Neutralization of Special Elements in Command",
                "CWE-78: OS Command Injection",
                "CWE-79: Cross-site Scripting (XSS)",
                "CWE-80: Improper Neutralization of Script-Related HTML Tags",
                "CWE-83: Improper Neutralization of Script in Attributes",
                "CWE-87: Improper Neutralization of Alternate XSS Syntax",
                "CWE-88: Improper Neutralization of Argument Delimiters",
                "CWE-89: SQL Injection",
                "CWE-90: LDAP Injection",
                "CWE-91: XML Injection",
                "CWE-93: Improper Neutralization of CRLF Sequences",
                "CWE-94: Improper Control of Generation of Code",
                "CWE-95: Improper Neutralization of Directives in Dynamically Evaluated Code",
                "CWE-96: Improper Neutralization of Directives in Statically Saved Code",
                "CWE-97: Improper Neutralization of Server-Side Includes (SSI)",
                "CWE-98: Improper Control of Filename for Include/Require Statement",
                "CWE-99: Improper Control of Resource Identifiers",
                "CWE-100: Improper Handling of Technology-Specific Special Elements",
                "CWE-113: Improper Neutralization of CRLF Sequences in HTTP Headers",
                "CWE-116: Improper Encoding or Escaping of Output",
                "CWE-138: Improper Neutralization of Special Elements",
                "CWE-184: Incomplete List of Disallowed Inputs",
                "CWE-470: Use of Externally-Controlled Input to Select Classes or Code",
                "CWE-471: Modification of Assumed-Immutable Data",
                "CWE-564: SQL Injection: Hibernate",
                "CWE-610: Externally Controlled Reference to a Resource",
                "CWE-643: Improper Neutralization of Data within XPath Expressions",
                "CWE-644: Improper Neutralization of HTTP Headers for Scripting Syntax",
                "CWE-652: Improper Neutralization of Data within XQuery Expressions",
                "CWE-917: Improper Neutralization of Special Elements in Expression Language",
                "CWE-943: Improper Neutralization of Special Elements in Data Query Logic"
            ],
            attack_examples=[
                {
                    "name": "SQL Injection",
                    "code": """
# Vulnerable code
username = request.POST.get('username')
password = request.POST.get('password')
query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
result = db.execute(query)

# Attack payload: username = admin' OR '1'='1' --
# Resulting query: SELECT * FROM users WHERE username='admin' OR '1'='1' --' AND password=''
                    """
                },
                {
                    "name": "OS Command Injection",
                    "code": """
# Vulnerable code
filename = request.GET.get('file')
os.system(f'cat {filename}')

# Attack: ?file=test.txt; rm -rf /
# Executed: cat test.txt; rm -rf /
                    """
                },
                {
                    "name": "NoSQL Injection (MongoDB)",
                    "code": """
# Vulnerable code
username = request.json['username']
password = request.json['password']
user = db.users.find_one({'username': username, 'password': password})

# Attack payload:
{
  "username": {"$ne": null},
  "password": {"$ne": null}
}
# Returns first user in database
                    """
                }
            ],
            remediation={
                "immediate": [
                    "Use parameterized queries (prepared statements) everywhere",
                    "Input validation with whitelist approach",
                    "Escape special characters in user input",
                    "Implement least privilege database accounts"
                ],
                "short_term": [
                    "Use ORM frameworks (SQLAlchemy, Hibernate, Entity Framework)",
                    "Implement strict input validation with regex patterns",
                    "Use safe APIs that avoid interpreter entirely",
                    "Sanitize and validate all user inputs"
                ],
                "long_term": [
                    "Implement input validation framework across entire application",
                    "Use static application security testing (SAST) tools",
                    "Conduct regular penetration testing",
                    "Implement web application firewall (WAF) with injection rules"
                ]
            },
            secure_code_examples=[
                {
                    "language": "Python (SQLAlchemy)",
                    "code": """
# Secure SQL query with parameterization
from sqlalchemy import text

def authenticate_user(username, password):
    # Use parameterized query
    query = text("SELECT * FROM users WHERE username = :username AND password = :password")
    result = db.session.execute(query, {'username': username, 'password': password})
    return result.fetchone()

# Even better: Use ORM
user = User.query.filter_by(username=username, password=hashed_password).first()
                    """
                },
                {
                    "language": "Python (Subprocess)",
                    "code": """
# Secure OS command execution
import subprocess
import shlex

def process_file(filename):
    # Whitelist allowed characters
    if not re.match(r'^[a-zA-Z0-9_.-]+$', filename):
        raise ValueError("Invalid filename")

    # Use array form (no shell=True)
    result = subprocess.run(
        ['cat', filename],
        capture_output=True,
        text=True,
        timeout=5
    )
    return result.stdout
                    """
                },
                {
                    "language": "JavaScript (Node.js)",
                    "code": """
// Secure MongoDB query
const { MongoClient } = require('mongodb');

async function authenticateUser(username, password) {
  // Use parameterized query
  const user = await db.collection('users').findOne({
    username: username,  // Direct value, not operator
    password: password
  });

  return user;
}

// For complex queries, validate input types
function validateLoginInput(data) {
  if (typeof data.username !== 'string' || typeof data.password !== 'string') {
    throw new Error('Invalid input types');
  }
  return data;
}
                    """
                }
            ],
            testing_checklist=[
                "Test SQL injection in all input fields",
                "Test NoSQL injection (MongoDB, Cassandra)",
                "Test OS command injection",
                "Test LDAP injection",
                "Test XML injection (XXE)",
                "Test XSS (reflected, stored, DOM-based)",
                "Test template injection (SSTI)",
                "Test expression language injection",
                "Use automated tools (SQLMap, XSStrike, Commix)",
                "Test with polyglot payloads"
            ]
        ))

        # Build PDF
        doc.build(story)
        logger.info(f"OWASP Top 10 playbook created: {filename}")

    def _create_owasp_section(self, category, title, risk_level, description,
                             common_weaknesses, attack_examples, remediation,
                             secure_code_examples, testing_checklist):
        """Create a section for one OWASP category"""
        story = []

        # Section header
        story.append(Paragraph(f"{category}: {title}", self.styles['Heading1']))
        story.append(Paragraph(f"<b>Risk Level:</b> <font color='red'>{risk_level}</font>",
                              self.styles['Normal']))
        story.append(Spacer(1, 0.2*inch))

        # Description
        story.append(Paragraph("<b>Description</b>", self.styles['SectionHeader']))
        story.append(Paragraph(description.strip(), self.styles['BodyText']))
        story.append(Spacer(1, 0.1*inch))

        # Common Weaknesses (CWEs)
        story.append(Paragraph("<b>Common Weakness Enumerations (CWEs)</b>", self.styles['SectionHeader']))
        for cwe in common_weaknesses[:10]:  # Show top 10
            story.append(Paragraph(f"• {cwe}", self.styles['Normal']))
        story.append(Spacer(1, 0.1*inch))

        # Attack Examples
        story.append(Paragraph("<b>Attack Examples</b>", self.styles['SectionHeader']))
        for example in attack_examples:
            story.append(Paragraph(f"<b>{example['name']}</b>", self.styles['Normal']))
            story.append(Paragraph(f"<font name='Courier' size='8'>{example['code']}</font>",
                                  self.styles['Code']))
            story.append(Spacer(1, 0.05*inch))

        # Remediation
        story.append(Paragraph("<b>Remediation Strategy</b>", self.styles['SectionHeader']))

        story.append(Paragraph("<i>Immediate (2-4 hours):</i>", self.styles['Normal']))
        for step in remediation['immediate']:
            story.append(Paragraph(f"• {step}", self.styles['Normal']))

        story.append(Paragraph("<i>Short-term (1-3 days):</i>", self.styles['Normal']))
        for step in remediation['short_term']:
            story.append(Paragraph(f"• {step}", self.styles['Normal']))

        story.append(Paragraph("<i>Long-term (1-2 weeks):</i>", self.styles['Normal']))
        for step in remediation['long_term']:
            story.append(Paragraph(f"• {step}", self.styles['Normal']))
        story.append(Spacer(1, 0.1*inch))

        # Secure Code Examples
        story.append(Paragraph("<b>Secure Code Examples</b>", self.styles['SectionHeader']))
        for example in secure_code_examples:
            story.append(Paragraph(f"<b>{example['language']}</b>", self.styles['Normal']))
            story.append(Paragraph(f"<font name='Courier' size='7'>{example['code']}</font>",
                                  self.styles['Code']))
            story.append(Spacer(1, 0.05*inch))

        # Testing Checklist
        story.append(Paragraph("<b>Security Testing Checklist</b>", self.styles['SectionHeader']))
        for item in testing_checklist:
            story.append(Paragraph(f"☐ {item}", self.styles['Normal']))

        story.append(PageBreak())
        return story

    # ==========================================================================
    # CWE TOP 25 PLAYBOOK
    # ==========================================================================

    def generate_cwe_top25_playbook(self):
        """Generate CWE Top 25 Most Dangerous Software Weaknesses Playbook"""
        logger.info("Generating CWE Top 25 playbook...")

        filename = self.output_dir / "CWE_Top25_2023_Playbook.pdf"
        doc = SimpleDocTemplate(str(filename), pagesize=letter)
        story = []

        # Title
        story.append(Paragraph("CWE Top 25 Most Dangerous", self.styles['CustomTitle']))
        story.append(Paragraph("Software Weaknesses 2023", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d')}", self.styles['Normal']))
        story.append(PageBreak())

        # Add top CWEs with detailed info
        top_cwes = [
            {
                "rank": 1,
                "cwe_id": "CWE-79",
                "name": "Cross-site Scripting (XSS)",
                "score": 45.54,
                "description": "The product does not neutralize or incorrectly neutralizes user-controllable input before it is placed in output that is used as a web page served to other users.",
                "examples": ["Reflected XSS", "Stored XSS", "DOM-based XSS"],
                "languages": ["JavaScript", "PHP", "ASP.NET", "Java"]
            },
            {
                "rank": 2,
                "cwe_id": "CWE-787",
                "name": "Out-of-bounds Write",
                "score": 46.17,
                "description": "The product writes data past the end, or before the beginning, of the intended buffer.",
                "examples": ["Buffer overflow", "Stack overflow", "Heap overflow"],
                "languages": ["C", "C++", "Assembly"]
            },
            {
                "rank": 3,
                "cwe_id": "CWE-89",
                "name": "SQL Injection",
                "score": 34.27,
                "description": "The product constructs all or part of an SQL command using externally-influenced input, but does not neutralize special elements.",
                "examples": ["Classic SQL Injection", "Blind SQL Injection", "Second-order SQL Injection"],
                "languages": ["PHP", "Java", "Python", "ASP.NET"]
            },
        ]

        for cwe in top_cwes:
            story.append(Paragraph(
                f"#{cwe['rank']}: {cwe['cwe_id']} - {cwe['name']}",
                self.styles['Heading1']
            ))
            story.append(Paragraph(f"<b>Score:</b> {cwe['score']}", self.styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

            story.append(Paragraph("<b>Description:</b>", self.styles['SectionHeader']))
            story.append(Paragraph(cwe['description'], self.styles['BodyText']))
            story.append(Spacer(1, 0.1*inch))

            story.append(Paragraph("<b>Common Examples:</b>", self.styles['Normal']))
            for ex in cwe['examples']:
                story.append(Paragraph(f"• {ex}", self.styles['Normal']))

            story.append(Paragraph("<b>Affected Languages:</b>", self.styles['Normal']))
            story.append(Paragraph(f"{', '.join(cwe['languages'])}", self.styles['Normal']))
            story.append(PageBreak())

        doc.build(story)
        logger.info(f"CWE Top 25 playbook created: {filename}")

    # ==========================================================================
    # REMEDIATION GUIDE PLAYBOOK
    # ==========================================================================

    def generate_remediation_playbook(self):
        """Generate comprehensive remediation guide"""
        logger.info("Generating remediation playbook...")

        filename = self.output_dir / "Remediation_Guide_Playbook.pdf"
        doc = SimpleDocTemplate(str(filename), pagesize=letter)
        story = []

        # Title
        story.append(Paragraph("Security Remediation Guide", self.styles['CustomTitle']))
        story.append(Paragraph("3-Phase Approach", self.styles['CustomTitle']))
        story.append(PageBreak())

        # Content here...
        story.append(Paragraph("Phase 1: Immediate Response (2-4 hours)", self.styles['Heading1']))
        story.append(Paragraph(
            "Quick fixes to minimize immediate risk while proper fix is developed.",
            self.styles['BodyText']
        ))

        doc.build(story)
        logger.info(f"Remediation playbook created: {filename}")

    # ==========================================================================
    # INCIDENT RESPONSE PLAYBOOK
    # ==========================================================================

    def generate_incident_response_playbook(self):
        """Generate incident response playbook"""
        logger.info("Generating incident response playbook...")

        filename = self.output_dir / "Incident_Response_Playbook.pdf"
        doc = SimpleDocTemplate(str(filename), pagesize=letter)
        story = []

        # Title
        story.append(Paragraph("Security Incident Response", self.styles['CustomTitle']))
        story.append(Paragraph("Playbook", self.styles['CustomTitle']))
        story.append(PageBreak())

        # Phases
        phases = [
            {
                "name": "1. Preparation",
                "steps": [
                    "Establish incident response team (IRT)",
                    "Define roles and responsibilities",
                    "Setup communication channels",
                    "Prepare incident response toolkit",
                    "Conduct tabletop exercises"
                ]
            },
            {
                "name": "2. Detection & Analysis",
                "steps": [
                    "Monitor security alerts from SIEM",
                    "Analyze suspicious activities",
                    "Determine incident severity",
                    "Document initial findings",
                    "Activate incident response team"
                ]
            },
            {
                "name": "3. Containment",
                "steps": [
                    "Isolate affected systems",
                    "Preserve evidence",
                    "Implement temporary fixes",
                    "Monitor for lateral movement",
                    "Update detection rules"
                ]
            },
            {
                "name": "4. Eradication",
                "steps": [
                    "Remove malware/backdoors",
                    "Patch vulnerabilities",
                    "Strengthen security controls",
                    "Reset compromised credentials",
                    "Verify clean state"
                ]
            },
            {
                "name": "5. Recovery",
                "steps": [
                    "Restore systems from clean backups",
                    "Monitor for re-infection",
                    "Gradually restore services",
                    "Verify business operations",
                    "Update security posture"
                ]
            },
            {
                "name": "6. Post-Incident",
                "steps": [
                    "Conduct post-mortem analysis",
                    "Document lessons learned",
                    "Update incident response plan",
                    "Improve detection capabilities",
                    "Provide security awareness training"
                ]
            }
        ]

        for phase in phases:
            story.append(Paragraph(phase['name'], self.styles['Heading1']))
            for step in phase['steps']:
                story.append(Paragraph(f"• {step}", self.styles['Normal']))
            story.append(Spacer(1, 0.2*inch))

        doc.build(story)
        logger.info(f"Incident response playbook created: {filename}")


def main():
    """Generate all security playbooks"""
    generator = SecurityPlaybookGenerator()
    generator.generate_all_playbooks()
    print("✓ All security playbooks generated successfully!")


if __name__ == "__main__":
    main()
