from config import DEFAULT_TOPIC, SOURCES, OUTPUT_FORMATS


def main():
    print("Market Intelligence Agent started.")
    print(f"Topic: {DEFAULT_TOPIC}")

    print("\nInitial Sources:")
    for source in SOURCES:
        print(f"- {source['name']}: {source['url']}")

    print("\nExpected Outputs:")
    for output in OUTPUT_FORMATS:
        print(f"- {output}")


if __name__ == "__main__":
    main()
