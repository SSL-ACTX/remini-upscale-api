# Remini Unofficial API

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)

A Python library for enhancing and stylizing images using the unofficial Remini API. This package automates the entire process, including authentication, image uploading, processing, and downloading the final result.

> ### Disclaimer
> This is an unofficial library and is not affiliated with, endorsed, or sponsored by Remini. The Remini API is not publicly documented and may change at any time, which could break this library. Use this software responsibly and at your own risk.

### Features

-   Robust authentication flow matching the latest API requirements.
-   Automatic session handling and token caching in a temporary directory.
-   Perform standard image enhancement to improve quality and resolution.
-   Apply artistic styles like 'toon' to images.
-   Fully `asyncio` based for modern, non-blocking applications.

### Installation

You can install this library directly from the GitHub repository using `pip`.

```bash
pip install git+https://github.com/SSL-ACTX/remini-upscale-api.git
```

### Basic Usage

The library provides two main functions: `process()` for standard enhancement and `stylize()` for applying artistic effects.

Here is a complete example. Edit the file paths, uncomment the option you want to use, and run the script.

```python
# test.py
import asyncio
from remini import Remini, ReminiError

async def main():
    input_image_path = "input.jpg"

    try:
        # Initialize the Remini client.
        client = Remini()

        # Option 1: Standard Enhancement (upscale)
        print("Starting standard enhancement...")
        await client.process(image_path=input_image_path, output_path="enhanced_output.jpg")

        # Option 2: Stylization (e.g., 'toon') - looks horrible, so not really useful lmao
        # print("Starting stylization...")
        # await client.stylize(image_path=input_image_path, style="toon", output_path="stylized_output.jpg")

        print("\n✅ Process finished successfully!")

    except FileNotFoundError:
        print(f"❌ Error: The input file was not found at '{input_image_path}'")
    except ReminiError as e:
        print(f"❌ An API error occurred: {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

### How to Run the Example

1.  Make sure you have the library installed.
2.  Save the code above as `example.py`.
3.  Edit the `input_image_path` variable and uncomment your desired operation (`process` or `stylize`).
4.  Run the script from your terminal:
    ```bash
    python test.py
    ```

### Contributing

Contributions are welcome! If you find a bug, have a feature request, or want to improve the code, please open an issue or submit a pull request on the GitHub repository.

### License

This project is licensed under the **Mozilla Public License 2.0**. See [LICENSE](LICENSE)
