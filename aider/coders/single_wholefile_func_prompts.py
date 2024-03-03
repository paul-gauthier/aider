# flake8: noqa: E501

from .base_prompts import CoderPrompts
from . import prompt_manager



class SingleWholeFileFunctionPrompts(CoderPrompts):
    yaml_prompt_entry = prompt_manager.get_prompt_value('EditBlockFunctionPrompts', 'main_system')
    main_system = yaml_prompt_entry if yaml_prompt_entry else """Act as an expert software developer.
Take requests for changes to the supplied code.
If the request is ambiguous, ask questions.

Once you understand the request you MUST use the `write_file` function to update the file to make the changes.
"""

    system_reminder = """
ONLY return code using the `write_file` function.
NEVER return code outside the `write_file` function.
"""

    files_content_prefix = "Here is the current content of the file:\n"
    files_no_full_files = "I am not sharing any files yet."

    redacted_edit_message = "No changes are needed."

    # TODO: should this be present for using this with gpt-4?
    repo_content_prefix = None

    # TODO: fix the chat history, except we can't keep the whole file
