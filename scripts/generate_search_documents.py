import argparse
import json
import os
import random
import sys
import uuid

TOPICS = [
    "private cars downtown",
    "public transit investment",
    "urban green space",
    "bike lane expansion",
    "parking restrictions",
    "electric vehicle charging",
    "pedestrian-only zones",
    "micro-mobility integration",
    "city air quality",
    "transit affordability",
]

SOURCES = [
    "Urban Planning Review",
    "City Transit Journal",
    "WHO",
    "Mobility Futures",
    "Policy Brief",
    "Sustainability Digest",
    "Economic Outlook",
    "Neighborhood Times",
    "Transport Analytics",
    "Smart City Insights",
]

CATEGORIES = [
    "transport",
    "environment",
    "economics",
    "public health",
    "urban design",
    "policy",
    "community",
    "technology",
]

STATEMENTS = [
    "Research suggests that {topic} can {effect}.",
    "Experts say the city must {action} to improve {topic} outcomes.",
    "A strong {topic} strategy can help {benefit}.",
    "One study found that {topic} impacts {impact}.",
    "Many planners believe changing {topic} will {result}.",
    "Evidence shows that {topic} influences {impact}.",
    "Cities with better {topic} often report {benefit}.",
    "Policymakers are considering how {topic} affects {impact}.",
]

EFFECTS = [
    "reduce traffic congestion",
    "improve air quality",
    "boost downtown commerce",
    "increase pedestrian safety",
    "lower carbon emissions",
    "enhance quality of life",
    "strengthen transit use",
    "support equitable access",
]

ACTIONS = [
    "reallocate street space",
    "invest in transit",
    "create more bike-friendly routes",
    "limit private vehicle access",
    "update parking policy",
    "expand green infrastructure",
    "design safer intersections",
    "encourage walking and cycling",
]

BENEFITS = [
    "health outcomes",
    "economic resilience",
    "community wellbeing",
    "social equity",
    "urban mobility",
    "public safety",
    "environmental sustainability",
    "local business vitality",
]

IMPACTS = [
    "air quality",
    "traffic flow",
    "public health",
    "real estate value",
    "citizen satisfaction",
    "operational efficiency",
    "social inclusion",
    "travel behavior",
]

EXAMPLES = [
    "Cities are experimenting with congestion charges and pedestrian plazas.",
    "Data from recent pilot programs show measurable benefits for pedestrians.",
    "The policy trend is shifting toward more people-centered street design.",
    "Early findings indicate that transit ridership rises when cars are restricted.",
    "Communities often see quieter streets and safer crossings after implementation.",
    "Lower emissions are a common result of reducing private vehicle use.",
]


def build_document(index: int) -> dict:
    topic = random.choice(TOPICS)
    source = random.choice(SOURCES)
    category = random.choice(CATEGORIES)
    statements = random.sample(STATEMENTS, 2)
    content = " ".join(
        stmt.format(
            topic=topic,
            effect=random.choice(EFFECTS),
            action=random.choice(ACTIONS),
            benefit=random.choice(BENEFITS),
            impact=random.choice(IMPACTS),
            result=random.choice(EFFECTS),
        )
        for stmt in statements
    )
    content += " " + random.choice(EXAMPLES)

    title = f"{topic.capitalize()} insights"
    doc_id = f"doc-{index:03d}"
    return {
        "@search.action": "upload",
        "id": doc_id,
        "title": title,
        "content": content,
        "source": source,
        "category": category,
    }


def generate_docs(count: int) -> list:
    return [build_document(i + 1) for i in range(count)]


def upload_docs(endpoint: str, api_key: str, index: str, docs: list) -> dict:
    url = f"{endpoint.rstrip('/')}/indexes/{index}/docs/index?api-version=2021-04-30-Preview"
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }
    payload = {"value": docs}

    try:
        import requests
    except ImportError:
        print("ERROR: requests is required to upload documents. Install it with pip.")
        sys.exit(1)

    response = requests.post(url, json=payload, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate sample Azure Search documents and optionally upload them to an index."
    )
    parser.add_argument("--count", type=int, default=50, help="Number of documents to generate.")
    parser.add_argument("--output", type=str, default="sample_search_documents.json", help="Local JSON file path for generated documents.")
    parser.add_argument("--upload", action="store_true", help="Upload generated documents to Azure Search using environment variables.")
    parser.add_argument("--endpoint", type=str, help="Azure Search endpoint URL. Overrides AZURE_SEARCH_ENDPOINT.")
    parser.add_argument("--key", type=str, help="Azure Search API key. Overrides AZURE_SEARCH_KEY.")
    parser.add_argument("--index", type=str, help="Azure Search index name. Overrides AZURE_SEARCH_INDEX.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    docs = generate_docs(args.count)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"value": docs}, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(docs)} documents in '{args.output}'.")

    if args.upload:
        endpoint = args.endpoint or os.getenv("AZURE_SEARCH_ENDPOINT")
        api_key = args.key or os.getenv("AZURE_SEARCH_KEY")
        index = args.index or os.getenv("AZURE_SEARCH_INDEX")

        if not endpoint or not api_key or not index:
            print("ERROR: Missing Azure Search configuration. Set AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, AZURE_SEARCH_INDEX, or use command-line options.")
            sys.exit(1)

        print("Uploading documents to Azure Search index...")
        result = upload_docs(endpoint, api_key, index, docs)
        print("Upload response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
