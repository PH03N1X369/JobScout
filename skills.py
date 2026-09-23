"""Skill and job-title vocabularies, plus helpers to find them in free text.

Matching is dictionary based: each canonical skill has a list of aliases that
are searched with word-boundary-aware regexes. Short, ambiguous names such as
"C", "R" and "Go" are only matched case-sensitively inside list-like context
("Python, Go, Rust") to avoid false positives in ordinary prose.
"""

import re
from functools import lru_cache

SKILLS = {
    # Programming languages
    "Python": ["python"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js", "es6", "ecmascript"],
    "TypeScript": ["typescript"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp"],
    "Rust": ["rust"],
    "Ruby": ["ruby"],
    "PHP": ["php"],
    "Swift": ["swift"],
    "Kotlin": ["kotlin"],
    "Scala": ["scala"],
    "MATLAB": ["matlab"],
    "Perl": ["perl"],
    "Dart": ["dart"],
    "Elixir": ["elixir"],
    "Haskell": ["haskell"],
    "Objective-C": ["objective-c", "objective c"],
    "Bash": ["bash", "shell scripting"],
    "PowerShell": ["powershell"],
    "SQL": ["sql"],
    "VBA": ["vba"],
    "Solidity": ["solidity"],
    # Frontend
    "React": ["react", "react.js", "reactjs"],
    "Angular": ["angular", "angularjs"],
    "Vue.js": ["vue", "vue.js", "vuejs"],
    "Svelte": ["svelte", "sveltekit"],
    "Next.js": ["next.js", "nextjs"],
    "Redux": ["redux"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "Sass": ["sass", "scss"],
    "Tailwind CSS": ["tailwind", "tailwindcss"],
    "jQuery": ["jquery"],
    "Webpack": ["webpack"],
    "GraphQL": ["graphql"],
    "REST APIs": ["rest api", "rest apis", "restful"],
    "Accessibility": ["accessibility", "wcag", "a11y"],
    # Backend
    "Node.js": ["node.js", "nodejs"],
    "Express": ["express.js", "expressjs"],
    "NestJS": ["nestjs", "nest.js"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Spring Boot": ["spring boot", "springboot", "spring framework"],
    "Ruby on Rails": ["ruby on rails", "rails"],
    "Laravel": ["laravel"],
    ".NET": [".net", "asp.net", "dotnet", ".net core"],
    "Microservices": ["microservices", "microservice"],
    "gRPC": ["grpc"],
    "Kafka": ["kafka"],
    "RabbitMQ": ["rabbitmq"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch", "opensearch"],
    # Databases & warehouses
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "SQL Server": ["sql server", "mssql", "t-sql"],
    "Oracle": ["oracle"],
    "DynamoDB": ["dynamodb"],
    "Cassandra": ["cassandra"],
    "Snowflake": ["snowflake"],
    "BigQuery": ["bigquery"],
    "Redshift": ["redshift"],
    # Cloud & DevOps
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Terraform": ["terraform"],
    "Ansible": ["ansible"],
    "Jenkins": ["jenkins"],
    "GitHub Actions": ["github actions"],
    "CI/CD": ["ci/cd", "cicd", "continuous integration", "continuous delivery", "continuous deployment"],
    "Linux": ["linux", "unix"],
    "Git": ["git"],
    "Serverless": ["serverless", "aws lambda"],
    "Prometheus": ["prometheus"],
    "Grafana": ["grafana"],
    "Datadog": ["datadog"],
    "Nginx": ["nginx"],
    "Helm": ["helm"],
    "Observability": ["observability"],
    # Data & ML
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "neural networks"],
    "AI": ["artificial intelligence", "ai"],
    "LLMs": ["llm", "llms", "large language model", "large language models", "generative ai", "genai"],
    "NLP": ["nlp", "natural language processing"],
    "Computer Vision": ["computer vision", "opencv"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Spark": ["spark", "pyspark", "apache spark"],
    "Hadoop": ["hadoop"],
    "Airflow": ["airflow"],
    "dbt": ["dbt"],
    "ETL": ["etl", "elt", "data pipeline", "data pipelines"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Data Visualization": ["data visualization", "data visualisation"],
    "Tableau": ["tableau"],
    "Power BI": ["power bi", "powerbi"],
    "Looker": ["looker"],
    "Excel": ["excel"],
    "Statistics": ["statistics", "statistical"],
    "A/B Testing": ["a/b testing", "a/b tests", "experimentation"],
    "Data Modeling": ["data modeling", "data modelling"],
    "MLOps": ["mlops"],
    "Databricks": ["databricks"],
    "LangChain": ["langchain"],
    "Hugging Face": ["hugging face", "huggingface"],
    # Mobile
    "iOS": ["ios"],
    "Android": ["android"],
    "React Native": ["react native"],
    "Flutter": ["flutter"],
    "SwiftUI": ["swiftui"],
    # Testing & QA
    "Unit Testing": ["unit testing", "unit tests", "tdd", "test-driven"],
    "Jest": ["jest"],
    "Cypress": ["cypress"],
    "Selenium": ["selenium"],
    "Playwright": ["playwright"],
    "pytest": ["pytest"],
    "JUnit": ["junit"],
    "Test Automation": ["test automation", "automated testing"],
    "QA": ["quality assurance", "qa"],
    # Security
    "Cybersecurity": ["cybersecurity", "cyber security", "information security", "infosec"],
    "Penetration Testing": ["penetration testing", "pentesting", "pen testing"],
    "Splunk": ["splunk"],
    "SIEM": ["siem"],
    "IAM": ["iam", "identity and access management"],
    "OAuth/SSO": ["oauth", "oauth2", "openid connect", "saml", "sso"],
    "Network Security": ["network security", "firewalls"],
    "Compliance": ["soc 2", "soc2", "iso 27001", "gdpr", "hipaa", "pci dss"],
    # Design
    "Figma": ["figma"],
    "Adobe XD": ["adobe xd"],
    "Photoshop": ["photoshop"],
    "Illustrator": ["adobe illustrator"],
    "InDesign": ["indesign"],
    "UX Design": ["ux", "user experience", "ux design"],
    "UI Design": ["ui design", "user interface design", "ui/ux", "ux/ui"],
    "User Research": ["user research", "usability testing"],
    "Prototyping": ["prototyping", "wireframing", "wireframes"],
    "Design Systems": ["design system", "design systems"],
    "Motion Design": ["motion design", "after effects"],
    "Graphic Design": ["graphic design"],
    # Product & project management
    "Product Management": ["product management", "product roadmap", "roadmapping"],
    "Project Management": ["project management", "pmp"],
    "Agile": ["agile"],
    "Scrum": ["scrum"],
    "Kanban": ["kanban"],
    "Jira": ["jira"],
    "Confluence": ["confluence"],
    "Stakeholder Management": ["stakeholder management"],
    "Requirements Gathering": ["requirements gathering", "business requirements", "user stories"],
    "OKRs": ["okr", "okrs"],
    # Marketing
    "SEO": ["seo", "search engine optimization"],
    "SEM/PPC": ["sem", "google ads", "ppc", "paid search"],
    "Content Marketing": ["content marketing", "content strategy"],
    "Social Media": ["social media"],
    "Email Marketing": ["email marketing", "mailchimp", "klaviyo"],
    "Google Analytics": ["google analytics", "ga4"],
    "HubSpot": ["hubspot"],
    "Marketing Automation": ["marketing automation", "marketo", "pardot"],
    "Copywriting": ["copywriting"],
    "Branding": ["brand strategy", "branding"],
    "Growth Marketing": ["growth marketing", "growth hacking"],
    "Paid Social": ["paid social", "facebook ads", "meta ads"],
    # Sales & customer
    "Salesforce": ["salesforce", "sfdc"],
    "CRM": ["crm"],
    "B2B Sales": ["b2b sales", "saas sales"],
    "Lead Generation": ["lead generation", "prospecting"],
    "Account Management": ["account management"],
    "Customer Success": ["customer success"],
    "Customer Support": ["customer support", "customer service", "zendesk"],
    "Negotiation": ["negotiation"],
    "Business Development": ["business development"],
    # Finance & accounting
    "Financial Modeling": ["financial modeling", "financial modelling", "financial analysis"],
    "Accounting": ["accounting", "gaap", "ifrs"],
    "Bookkeeping": ["bookkeeping", "quickbooks", "xero"],
    "FP&A": ["fp&a", "budgeting", "forecasting"],
    "Auditing": ["auditing", "internal audit"],
    "Tax": ["taxation", "tax preparation"],
    "SAP": ["sap"],
    "Risk Management": ["risk management"],
    "Payroll": ["payroll"],
    # People
    "Recruiting": ["recruiting", "recruitment", "talent acquisition"],
    "HRIS": ["hris", "workday", "bamboohr"],
    "Employee Relations": ["employee relations"],
    "People Management": ["people management", "team leadership", "mentoring"],
    # Healthcare
    "Patient Care": ["patient care"],
    # Bare "emr" is left out: in tech resumes it usually means AWS Elastic MapReduce.
    "EHR/EMR": ["ehr", "epic systems", "cerner", "electronic health records", "electronic medical records"],
    "Nursing": ["nursing", "registered nurse"],
    "Clinical Research": ["clinical research", "clinical trials"],
    "Medical Coding": ["medical coding", "icd-10"],
    # Operations
    "Supply Chain": ["supply chain", "logistics", "procurement"],
    "Lean Six Sigma": ["lean six sigma", "six sigma", "lean manufacturing"],
    "Inventory Management": ["inventory management"],
    "ERP": ["erp", "netsuite"],
    # Other
    "Technical Writing": ["technical writing"],
    "Teaching": ["curriculum development", "lesson planning"],
    "Localization": ["localization", "localisation"],
    "Video Editing": ["video editing", "premiere pro", "final cut"],
    "Blockchain": ["blockchain", "web3", "smart contracts"],
    "Embedded Systems": ["embedded systems", "firmware", "rtos"],
    "IoT": ["iot", "internet of things"],
    "Networking": ["tcp/ip", "cisco", "ccna"],
    "Game Development": ["game development", "unity3d", "unreal engine"],
    "CAD": ["autocad", "solidworks"],
}

# Short, case-sensitive names that are only trusted inside list-like context in
# prose. Values are extra unambiguous aliases matched anywhere.
LIST_CONTEXT_SKILLS = {"C": [], "R": ["rstudio"], "Go": ["golang"]}

TITLES = {
    "Software Engineer": ["software engineer", "software developer", "software development engineer",
                          "application developer", "programmer"],
    "Frontend Developer": ["frontend developer", "front-end developer", "front end developer",
                           "frontend engineer", "front-end engineer", "front end engineer", "ui engineer",
                           "ui developer"],
    "Backend Developer": ["backend developer", "back-end developer", "back end developer",
                          "backend engineer", "back-end engineer", "back end engineer"],
    "Full Stack Developer": ["full stack developer", "full-stack developer", "fullstack developer",
                             "full stack engineer", "full-stack engineer", "fullstack engineer"],
    "Web Developer": ["web developer", "wordpress developer", "shopify developer"],
    "Mobile Developer": ["mobile developer", "mobile engineer", "ios developer", "ios engineer",
                         "android developer", "android engineer", "flutter developer"],
    "DevOps Engineer": ["devops engineer", "platform engineer", "infrastructure engineer",
                        "release engineer", "build engineer"],
    "Site Reliability Engineer": ["site reliability engineer", "sre"],
    "Cloud Engineer": ["cloud engineer", "cloud architect", "solutions architect"],
    "Data Scientist": ["data scientist", "applied scientist", "research scientist"],
    "Data Analyst": ["data analyst", "analytics analyst", "bi analyst", "business intelligence analyst",
                     "reporting analyst", "bi developer"],
    "Data Engineer": ["data engineer", "analytics engineer", "etl developer", "big data engineer"],
    "Machine Learning Engineer": ["machine learning engineer", "ml engineer", "ai engineer", "mlops engineer",
                                  "deep learning engineer"],
    "QA Engineer": ["qa engineer", "quality assurance engineer", "test engineer", "sdet", "qa analyst",
                    "software tester", "qa automation engineer", "automation tester"],
    "Security Engineer": ["security engineer", "security analyst", "cybersecurity analyst",
                          "information security analyst", "penetration tester", "soc analyst"],
    "Embedded Engineer": ["embedded engineer", "embedded software engineer", "firmware engineer"],
    "Engineering Manager": ["engineering manager", "director of engineering", "head of engineering",
                            "vp of engineering", "cto"],
    "Product Manager": ["product manager", "product owner", "associate product manager",
                        "technical product manager"],
    "Project Manager": ["project manager", "program manager", "delivery manager", "scrum master"],
    "UX Designer": ["ux designer", "ui/ux designer", "ux/ui designer", "user experience designer",
                    "ux researcher", "interaction designer"],
    "Product Designer": ["product designer", "ui designer", "visual designer"],
    "Graphic Designer": ["graphic designer", "brand designer", "motion designer"],
    "Business Analyst": ["business analyst", "systems analyst", "business systems analyst"],
    "Marketing Manager": ["marketing manager", "marketing specialist", "digital marketing manager",
                          "digital marketer", "growth marketer", "marketing coordinator", "brand manager",
                          "product marketing manager"],
    "SEO Specialist": ["seo specialist", "seo manager", "sem specialist"],
    "Content Writer": ["content writer", "copywriter", "content strategist", "content marketing manager",
                       "technical writer"],
    "Social Media Manager": ["social media manager", "community manager", "social media specialist"],
    "Sales Representative": ["sales representative", "account executive", "sales development representative",
                             "business development representative", "sales manager", "inside sales"],
    "Account Manager": ["account manager", "key account manager", "client manager"],
    "Customer Success Manager": ["customer success manager"],
    "Customer Support Specialist": ["customer support specialist", "customer service representative",
                                    "support specialist", "support engineer", "technical support",
                                    "help desk"],
    "Recruiter": ["recruiter", "talent acquisition specialist", "talent partner", "sourcer"],
    "HR Manager": ["hr manager", "human resources manager", "hr generalist", "hr business partner",
                   "people operations", "hr specialist"],
    "Accountant": ["accountant", "staff accountant", "bookkeeper", "auditor"],
    "Financial Analyst": ["financial analyst", "fp&a analyst", "finance manager", "investment analyst",
                          "financial controller"],
    "Operations Manager": ["operations manager", "operations analyst", "operations coordinator",
                           "supply chain manager", "logistics coordinator", "procurement specialist"],
    "Nurse": ["registered nurse", "nurse practitioner", "nurse"],
    "Teacher": ["teacher", "instructor", "tutor", "lecturer"],
    "Consultant": ["management consultant", "it consultant", "consultant"],
    "Administrative Assistant": ["administrative assistant", "executive assistant", "office manager",
                                 "virtual assistant"],
    "Game Developer": ["game developer", "game designer", "unity developer"],
    "Database Administrator": ["database administrator", "dba"],
    "Network Engineer": ["network engineer", "network administrator", "systems administrator", "sysadmin"],
}

TITLE_STOPWORDS = {"senior", "sr", "junior", "jr", "lead", "principal", "staff", "associate", "of", "and",
                   "the", "i", "ii", "iii", "head", "chief", "intern", "manager"}


def _alias_pattern(alias):
    # Custom boundaries so "c++", "c#", ".net" and "node.js" still match cleanly,
    # while "java" does not match inside "javascript".
    body = r"[\s\-]+".join(re.escape(part) for part in alias.split())
    return rf"(?<![a-z0-9]){body}(?![a-z0-9+#])"


def _alias_union(aliases):
    return "|".join(_alias_pattern(a.lower()) for a in aliases)


def _short_name_pattern(name, list_context):
    token = re.escape(name)
    tail = r"(?![A-Za-z0-9#+\-&'.])"
    if list_context:
        # "Python, Go, Rust" or "(C/C++)" but not "Go beyond" or "Vitamin C".
        core = rf"(?:[,/|(:•·]\s*{token}{tail}|(?<![A-Za-z0-9#+.\-]){token}\s*[,/|)])"
    else:
        core = rf"(?<![A-Za-z0-9#+.\-]){token}{tail}"
    extra = LIST_CONTEXT_SKILLS[name]
    return core + (f"|(?i:{_alias_union(extra)})" if extra else "")


@lru_cache(maxsize=None)
def skill_regex(name):
    """Regex for finding a skill in prose (resumes, job descriptions)."""
    if name in LIST_CONTEXT_SKILLS:
        return re.compile(_short_name_pattern(name, list_context=True))
    aliases = SKILLS.get(name) or [name.lower()]
    return re.compile(_alias_union(aliases), re.IGNORECASE)


@lru_cache(maxsize=None)
def skill_field_regexes(name):
    """(title_re, tags_re, desc_re) for matching a skill against a job posting.

    Short names get looser matching in titles ("Senior Go Engineer") and tags
    ("go"), and strict list-context matching in descriptions.
    """
    if name in LIST_CONTEXT_SKILLS:
        title_re = re.compile(_short_name_pattern(name, list_context=False))
        tags_re = re.compile(_alias_union([name.lower()] + LIST_CONTEXT_SKILLS[name]), re.IGNORECASE)
        return title_re, tags_re, skill_regex(name)
    r = skill_regex(name)
    return r, r, r


@lru_cache(maxsize=None)
def title_regex(name):
    aliases = TITLES.get(name) or [name.lower()]
    return re.compile(_alias_union(aliases), re.IGNORECASE)


@lru_cache(maxsize=None)
def keyword_regex(keyword):
    """Regex for a user keyword. Known skills/titles expand to all their aliases."""
    canonical = canonical_skill(keyword)
    if canonical in LIST_CONTEXT_SKILLS:
        # The user asked for it explicitly, so trust the bare word.
        return skill_field_regexes(canonical)[0]
    if canonical:
        return skill_regex(canonical)
    canonical = canonical_title(keyword)
    if canonical:
        return title_regex(canonical)
    return re.compile(_alias_pattern(keyword.lower()), re.IGNORECASE)


def _lookup(vocab, text):
    t = text.strip().lower()
    for name, aliases in vocab.items():
        if t == name.lower() or t in aliases:
            return name
    return None


def canonical_skill(text):
    t = text.strip().lower()
    for name, aliases in LIST_CONTEXT_SKILLS.items():
        if t == name.lower() or t in aliases:
            return name
    return _lookup(SKILLS, text)


def canonical_title(text):
    return _lookup(TITLES, text)


def title_tokens(text):
    return [t for t in re.findall(r"[a-z0-9+#]+", text.lower()) if t not in TITLE_STOPWORDS]


def extract_skills(text):
    """Return [{name, count}] for every known skill found in text, most frequent first."""
    found = []
    names = list(SKILLS) + list(LIST_CONTEXT_SKILLS)
    for name in names:
        hits = skill_regex(name).findall(text)
        if hits:
            found.append({"name": name, "count": len(hits)})
    found.sort(key=lambda s: (-s["count"], s["name"].lower()))
    return found


def extract_titles(text, limit=3):
    """Guess the candidate's job titles. Earlier mentions (headline, latest role) weigh more."""
    length = max(len(text), 1)
    scored = []
    for name in TITLES:
        score = 0.0
        for m in title_regex(name).finditer(text):
            score += 1 + 2 * (1 - m.start() / length)
        if score:
            scored.append((score, name))
    scored.sort(reverse=True)
    return [name for _, name in scored[:limit]]
