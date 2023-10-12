import sys

import boto3


def main() -> int:
    print("Hello World!")
    s3 = boto3.client("s3")
    with open("resources/test_files/example_data.txt", "r", encoding="utf-8") as file:
        file_data = file.read()
        response = s3.put_object(Body=file_data, Bucket="ignite-test-file-upload-bucket", Key="example_data.txt")
        print(response)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
