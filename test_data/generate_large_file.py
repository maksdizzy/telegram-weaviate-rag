#!/usr/bin/env python3
"""Generate a large Telegram export file for performance testing"""

import json
import random
from datetime import datetime, timedelta

def generate_large_telegram_export(num_messages=500):
    """Generate a large Telegram export with many messages"""

    users = [
        {"name": "Alice", "id": "user001"},
        {"name": "Bob", "id": "user002"},
        {"name": "Charlie", "id": "user003"},
        {"name": "Diana", "id": "user004"},
        {"name": "Eve", "id": "user005"},
        {"name": "Frank", "id": "user006"},
        {"name": "Grace", "id": "user007"},
        {"name": "Henry", "id": "user008"}
    ]

    message_templates = [
        "Hey everyone! How's your day going?",
        "Just finished a great meeting. Feeling productive!",
        "Anyone want to grab coffee later?",
        "I just discovered this amazing new restaurant.",
        "The weather is beautiful today, perfect for a walk.",
        "Working on an interesting project right now.",
        "Does anyone have recommendations for good books?",
        "Just watched an incredible movie last night.",
        "Planning a weekend trip, any suggestions?",
        "Had the best lunch today at that new place.",
        "Really enjoying this sunny weather.",
        "Just learned something fascinating today.",
        "Anyone else excited about the upcoming holidays?",
        "Trying out a new recipe tonight.",
        "Just finished a great workout at the gym.",
        "The traffic was terrible this morning.",
        "Found an amazing article about technology trends.",
        "Planning to redecorate my living room.",
        "Just got back from a wonderful vacation.",
        "Working late tonight on an important deadline.",
        "Can't believe how fast this week went by.",
        "Looking forward to the weekend activities.",
        "Just discovered a new podcast series.",
        "The sunrise this morning was absolutely stunning.",
        "Having a productive day of coding.",
        "Really enjoying this new music album.",
        "Planning a dinner party for next weekend.",
        "Just finished reading an excellent novel.",
        "The garden is looking beautiful this time of year.",
        "Working on learning a new programming language."
    ]

    topics = [
        ["coffee", "cafe", "espresso", "morning", "breakfast"],
        ["work", "project", "meeting", "deadline", "productivity"],
        ["movies", "entertainment", "weekend", "relaxation", "fun"],
        ["food", "restaurant", "cooking", "dinner", "lunch"],
        ["travel", "vacation", "trip", "adventure", "exploration"],
        ["technology", "coding", "programming", "innovation", "development"],
        ["books", "reading", "literature", "knowledge", "learning"],
        ["weather", "sunny", "beautiful", "nature", "outdoors"],
        ["fitness", "workout", "health", "gym", "exercise"],
        ["music", "concert", "album", "artist", "songs"]
    ]

    messages = []
    start_date = datetime(2024, 1, 1, 8, 0, 0)
    current_date = start_date

    for i in range(num_messages):
        user = random.choice(users)
        template = random.choice(message_templates)

        # Add some topic-specific variations
        if random.random() < 0.3:  # 30% chance to add topic keywords
            topic_words = random.choice(topics)
            topic_word = random.choice(topic_words)
            template += f" Really interested in {topic_word} lately."

        # Add some longer messages occasionally
        if random.random() < 0.2:  # 20% chance for longer message
            template += " " + random.choice(message_templates)

        # Increment time by 1-60 minutes randomly
        time_increment = timedelta(minutes=random.randint(1, 60))
        current_date += time_increment

        message = {
            "id": 2000 + i,
            "type": "message",
            "date": current_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "from": user["name"],
            "from_id": user["id"],
            "text": template
        }

        # Add reply occasionally
        if i > 0 and random.random() < 0.15:  # 15% chance to reply
            recent_msg_id = messages[random.randint(max(0, i-5), i-1)]["id"]
            message["reply_to_message_id"] = recent_msg_id

        messages.append(message)

    export_data = {
        "name": f"Large Test Chat - {num_messages} messages",
        "type": "group",
        "id": 555666777,
        "messages": messages
    }

    return export_data

if __name__ == "__main__":
    # Generate large file
    large_data = generate_large_telegram_export(500)

    with open("/home/maksdizzy/repos/1-research/telegram-weaviate-rag/test_data/large_telegram_export.json", "w", encoding="utf-8") as f:
        json.dump(large_data, f, ensure_ascii=False, indent=2)

    print(f"Generated large test file with {len(large_data['messages'])} messages")