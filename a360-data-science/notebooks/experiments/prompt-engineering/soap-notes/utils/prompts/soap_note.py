from json import JSONDecodeError, loads

from ..bedrock import extract_text_content_block


def format_soap_note(converse_response: dict) -> str:
    """A helper function to format SOAP note in JSON to a plaintext

    Arguments:
        converse_response: A complete response from the Bedrock Converse API.

    Returns:
        Either a formatted SOAP note or a raw JSON string if the
            deserealization fails.
    """
    model_message = extract_text_content_block(converse_response)["text"]
    json_start = model_message.find("{")
    json_end = model_message.rfind("}")
    soap_json_str = model_message[json_start:json_end + 1]
    try:
        soap_dict = loads(soap_json_str)
    except JSONDecodeError:
        return soap_json_str
    return "\n".join(
        [
            f"{section.title()}: {contents}"
            for section, contents in soap_dict.items()
        ]
    )