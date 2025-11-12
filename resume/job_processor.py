from openai import OpenAI
from models import JobDescription
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import hashlib
import threading


class JobProcessor:
    """Processes job descriptions and extracts structured information."""
    
    def __init__(self, 
                 model: str = "gpt-4o",
                 temperature: float = 0.3):
        """
        Initialize the job processor.
        
        Args:
            model: The OpenAI model to use for extraction
            temperature: Temperature for the model (lower = more deterministic)
        """
        self.model = model
        self.temperature = temperature
        self.openai = OpenAI()
        self._current_extraction_lock = threading.Lock()  # Lock for current extraction
        self._current_extraction_hash = None  # Hash of currently cached/being extracted input (URL or text)
        self._current_extraction_result = None  # Cached result for current job description
    
    def _get_text_hash(self, text: str) -> str:
        """Generate a hash for the job description text to use as cache key."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def extract_job_info(self, job_description_text: str) -> JobDescription:
        """
        Extract structured information from a job description.
        
        Args:
            job_description_text: The raw job description text
            
        Returns:
            JobDescription: Structured information extracted from the job posting
        """
        json_schema = json.dumps(JobDescription.model_json_schema(), indent=2)
        
        system_prompt = f"""Extract the following JSON fields from the job text.

Return ONLY valid JSON with missing fields as null or [].

{json_schema}"""

        user_message = f"""Job text:

{job_description_text}"""

        response = self.openai.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            text_format=JobDescription,
            temperature=self.temperature,
        )
        
        return response.output_parsed
    
    def is_usable(self, job_info: JobDescription) -> bool:
        """
        Check if JobDescription contains enough information for resume/cover letter generation.
        
        Returns True if ANY two of these conditions are met:
        - job_title is present (not None)
        - len(required_skills) >= 2
        - len(responsibilities) >= 2
        - description_summary is present and >= 40 chars
        
        Args:
            job_info: The JobDescription to validate
            
        Returns:
            bool: True if usable, False otherwise
        """
        conditions_met = 0
        
        # Check job_title
        if job_info.job_title is not None:
            conditions_met += 1
        
        # Check required_skills
        if len(job_info.required_skills) >= 2:
            conditions_met += 1
        
        # Check responsibilities
        if len(job_info.responsibilities) >= 2:
            conditions_met += 1
        
        # Check description_summary
        if job_info.description_summary is not None and len(job_info.description_summary) >= 40:
            conditions_met += 1
        
        return conditions_met >= 2
    
    def is_url(self, text: str) -> bool:
        """Check if the input text is a valid URL"""
        try:
            result = urlparse(text.strip())
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def scrape_webpage_simple(self, url: str) -> str | None:
        """
        Scrape content from a webpage URL.
        
        Args:
            url: The URL to scrape
            
        Returns:
            str: The scraped text content, or None if scraping fails
        """
        try:
            print(f"Scraping {url}")
            # Set headers to mimic a real browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Make the request
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an error for bad status codes
            
            # Parse the HTML
            soup = BeautifulSoup(response.content, 'html.parser')

            # Get all text content
            content = soup.get_text()
            
            # Clean up the content - remove extra whitespace
            content = ' '.join(content.split())
                
            return content
            
        except requests.RequestException as e:
            print(f"Request error for {url}: {e}")
            return None
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def process_job_posting(self, job_posting: str) -> str:
        """
        Process job posting input - scrape if URL, return as-is if text.
        
        Args:
            job_posting: The job posting text or URL
            
        Returns:
            str: The processed job posting text
            
        Raises:
            Exception: If URL scraping fails
        """
        if self.is_url(job_posting):
            print(f"Detected URL: {job_posting}")
            scraped_content = self.scrape_webpage_simple(job_posting.strip())
            if scraped_content is not None:
                print("Successfully scraped webpage content")
                return scraped_content
            else:
                print("Failed to scrape webpage - URL will not be processed")
                raise Exception("Could not scrape the provided URL. Please provide the job description as text instead.")
        else:
            print("Input is text, using as-is")
            return job_posting
    
    def process_and_extract_job_info(self, job_posting: str) -> JobDescription:
        """
        Process job posting (scrape if URL) and extract structured information.
        Uses caching and thread-safe locking to prevent duplicate API calls and scraping.
        Only caches the current job description - new descriptions clear the previous cache.
        
        Args:
            job_posting: The job posting text or URL
            
        Returns:
            JobDescription: Structured information extracted from the job posting
            
        Raises:
            ValueError: If the extracted job description does not contain enough information
        """
        # Hash the input (URL or text) for caching
        input_hash = self._get_text_hash(job_posting.strip())
        
        # Acquire lock for the entire operation
        with self._current_extraction_lock:
            # Check if this input is already cached
            if input_hash == self._current_extraction_hash and self._current_extraction_result is not None:
                print(f"Using cached extracted job info")
                return self._current_extraction_result
            
            # If different input, clear old cache
            if input_hash != self._current_extraction_hash:
                self._current_extraction_hash = input_hash
                self._current_extraction_result = None
            
            # Process and extract (lock is held, so concurrent requests will wait)
            try:
                # Process job posting (scrape if URL)
                raw_job_text = self.process_job_posting(job_posting)
                
                # Extract structured information
                print(f"Extracting job info from text")
                job_info = self.extract_job_info(raw_job_text)
                
                # Validate that we have enough information
                if not self.is_usable(job_info):
                    raise ValueError(
                        "The job description does not contain enough information for resume/cover letter generation. "
                        "Please ensure at least 2 of the following are present: "
                        "job title, at least 2 required skills, at least 2 responsibilities, or a description summary (40+ chars)."
                        f"Job info: {job_info.model_dump_json(indent=2)}"
                        f"Raw job text: {raw_job_text}"
                    )
                
                # Cache the result only if everything succeeded
                self._current_extraction_result = job_info
                
                print(f"Cached extracted job info")
                print(f"Job info: {job_info.model_dump_json(indent=2)}")
                return job_info
                
            except Exception as e:
                # If processing/extraction fails, clear the hash so next request can retry
                # This prevents getting stuck with a failed extraction state
                if self._current_extraction_hash == input_hash:
                    self._current_extraction_hash = None
                    self._current_extraction_result = None
                print(f"Error processing/extracting job info: {e}")
                raise

