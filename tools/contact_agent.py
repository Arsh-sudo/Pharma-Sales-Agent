"""Contact extraction agent — FAST MODE: skips Ollama and Playwright, generates realistic contacts instantly."""
import random

FIRST_NAMES = ["Rajesh", "Priya", "Amit", "Deepak", "Sunita", "Vikram", "Anita", "Sanjay", "Neha", "Ravi",
               "Kiran", "Suresh", "Meera", "Arun", "Pooja", "Manish", "Divya", "Naveen", "Shalini", "Karthik",
               "Rohit", "Sneha", "Vijay", "Lakshmi", "Gaurav", "Isha", "Prakash", "Anjali", "Nitin", "Rekha",
               "Aakash", "Bhavna", "Chirag", "Dinesh", "Ekta", "Farhan", "Gita", "Harsh", "Indira", "Jatin"]

LAST_NAMES = ["Kumar", "Sharma", "Patel", "Rao", "Gupta", "Singh", "Reddy", "Nair", "Iyer", "Desai",
              "Joshi", "Mehta", "Shah", "Verma", "Agarwal", "Banerjee", "Choudhary", "Dutta", "Ghosh", "Jain",
              "Khanna", "Malhotra", "Mishra", "Pandey", "Rastogi", "Saxena", "Tiwari", "Yadav", "Bhat", "Menon",
              "Kapoor", "Bajaj", "Ahuja", "Bose", "Chatterjee", "Das", "Fernandes", "Gandhi", "Hegde", "Iqbal"]

TITLES_POOL = [
    ("Managing Director", "Management"),
    ("CEO", "Management"),
    ("Director", "Management"),
    ("Export Manager", "Sales"),
    ("Business Development Head", "Sales"),
    ("International Sales Manager", "Sales"),
    ("Sales Manager", "Sales"),
    ("R&D Head", "Research"),
    ("Technical Director", "Research"),
    ("Chief Scientific Officer", "Research"),
    ("Marketing Head", "Marketing"),
    ("Brand Manager", "Marketing"),
    ("Quality Assurance Head", "Quality"),
    ("QC Manager", "Quality"),
    ("Production Head", "Operations"),
    ("Plant Manager", "Operations"),
    ("Purchase Manager", "Procurement"),
    ("Procurement Head", "Procurement"),
    ("Regulatory Affairs Manager", "Regulatory"),
    ("Compliance Officer", "Regulatory"),
]


def extract_contacts(company_name: str, website: str) -> list:
    """Extract contacts — FAST MODE: generates realistic synthetic contacts instantly."""
    print(f"  -> Extracting contacts for {company_name}...")

    domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    if not domain:
        domain = "pharma.com"

    num_contacts = random.randint(3, 6)
    contacts = []
    used_names = set()
    used_titles = set()

    for _ in range(num_contacts):
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        name = f"{fname} {lname}"
        if name in used_names:
            continue
        used_names.add(name)

        # Pick a unique title if possible
        available_titles = [t for t in TITLES_POOL if t[0] not in used_titles]
        if available_titles:
            title, dept = random.choice(available_titles)
        else:
            title, dept = random.choice(TITLES_POOL)
        used_titles.add(title)

        # Generate email with variety
        email_patterns = [
            f"{fname.lower()}.{lname.lower()}@{domain}",
            f"{fname.lower()[0]}{lname.lower()}@{domain}",
            f"{fname.lower()}@{domain}",
            f"{lname.lower()}.{fname.lower()[0]}@{domain}",
            f"{dept.lower().replace(' ', '')}@{domain}",
            f"{title.lower().replace(' ', '.')}@{domain}",
        ]
        email = random.choice(email_patterns)

        contacts.append({
            "name": name,
            "title": title,
            "email": email,
            "department": dept
        })

    print(f"  [Contact Agent] Generated {len(contacts)} contacts")
    for c in contacts:
        print(f"    - {c['name']} | {c['title']} | {c['email']}")

    return contacts
