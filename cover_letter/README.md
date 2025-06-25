# Cover Letter

This is a tool to help you create cover letters. It uses Agentic AI patterns, such as an evaluator optimizer, to ensure the quality of the AI generated output.

The app uses information in the about folder, so if you want to have the best output, input your personal infomation instead of the provided examples. You should also replace the example name with your own name.

To use the programm, navigate to this folder using command "cd cover_letter",
and run the following command: uv run cover_letter_builder.py

Now, click on the local website, and paste in either the job description, or a website link that contains the job descrition.

You will be able to observe the thinking process in the console, and AI will respond with a cover letter once it creates a cover letter that passes quality control.

Currently, the app uses gpt-4o for the creator model, and o4-mini as the evaluator model. You can change model type if you choose to do so. Be aware, that in order for the app to run, you will have to provide a .env file with your OPENAI_API_KEY.
