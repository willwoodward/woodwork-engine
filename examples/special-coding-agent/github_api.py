import requests
import os
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.environ.get("GITHUB_PAT")


def get_issue_information(repo, issue_number):
    """
    Get all information about a GitHub issue, including its description and comments.

    Args:
        repo (str): The repository in the format "owner/repo".
        issue_number (int): The issue number to retrieve information for.

    Returns:
        dict: A dictionary containing issue details and comments.
    """
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    # Get issue details
    issue_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    issue_response = requests.get(issue_url, headers=headers)
    issue_response.raise_for_status()

    issue_data = issue_response.json()

    # Get issue comments
    comments_url = issue_data.get("comments_url")
    comments_response = requests.get(comments_url, headers=headers)
    comments_response.raise_for_status()

    comments_data = comments_response.json()

    return {"issue": issue_data, "comments": comments_data}


def comment(repo, issue_number, comment_text):
    """
    Add a comment to a GitHub issue.

    Args:
        repo (str): The repository in the format "owner/repo".
        issue_number (int): The issue number to comment on.
        comment_text (str): The text of the comment.

    Returns:
        dict: The API response data for the created comment.
    """
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    payload = {"body": comment_text}

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return response.json()


def get_unread_comments(repo, issue_number, last_read_time):
    """
    Retrieve all comments on a GitHub issue that were created after a given timestamp.

    Args:
        repo (str): The repository in the format "owner/repo".
        issue_number (int): The issue number to retrieve comments for.
        last_read_time (str): ISO 8601 timestamp for the last read time.

    Returns:
        list: A list of unread comments.
    """
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    comments = response.json()
    unread_comments = [comment for comment in comments if comment["created_at"] > last_read_time]

    return unread_comments


def create_branch(repo, branch_name, base_branch):
    """
    Create a new branch in the GitHub repository.

    Args:
        repo (str): The repository in the format "owner/repo".
        branch_name (str): The name of the new branch to create.
        base_branch (str): The name of the branch to base the new branch on.

    Returns:
        dict: The API response data for the created branch.
    """
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    # Get the base branch's SHA
    url = f"https://api.github.com/repos/{repo}/git/refs/heads/{base_branch}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    base_branch_sha = response.json()["object"]["sha"]

    # Create the new branch
    url = f"https://api.github.com/repos/{repo}/git/refs"
    payload = {"ref": f"refs/heads/{branch_name}", "sha": base_branch_sha}

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return response.json()


def submit_pull_request(repo, branch_name, base_branch, issue_number, title):
    """
    Create a pull request associated with a GitHub issue.

    Args:
        repo (str): The repository in the format "owner/repo".
        branch_name (str): The branch containing the changes.
        base_branch (str): The branch to merge changes into.
        issue_number (int): The issue number to link with the pull request.
        title (str): The title of the pull request.

    Returns:
        dict: The API response data for the created pull request.
    """
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    url = f"https://api.github.com/repos/{repo}/pulls"

    body = f"Closes #{issue_number}"
    payload = {"title": title, "head": branch_name, "base": base_branch, "body": body}

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return response.json()
