import logging
import pathlib
import shutil

log = logging.getLogger(__name__)


def _rm_tree(path: pathlib.Path) -> None:
    """Recursively remove a directory if it exists."""
    try:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
                log.info("Removed directory: %s", path)
            else:
                path.unlink()
                log.info("Removed file: %s", path)
        else:
            log.debug("Path does not exist, skipping removal: %s", path)
    except Exception as e:
        log.warning("Failed to remove %s: %s", path, e)


def _cleanup_docker():
    """Attempt to stop/remove Docker containers and images that are tagged with 'woodwork'.

    We intentionally only target resources by tag now: containers are stopped/removed
    only when their image has a tag containing 'woodwork'. We no longer remove
    containers based on their name to avoid accidentally deleting unrelated containers
    whose names happen to contain the substring.
    """
    try:
        import docker
        from docker.errors import APIError
    except Exception as e:
        log.debug("Docker SDK not available or failed to import: %s", e)
        return

    try:
        client = docker.from_env()
    except Exception as e:
        log.debug("Could not initialise Docker client: %s", e)
        return

    # Stop and remove containers whose image tags include 'woodwork'
    try:
        for container in client.containers.list(all=True):
            try:
                image_tags = []
                try:
                    image_tags = container.image.tags or []
                except Exception:
                    pass

                # Only base matching on tags now
                matches = any("woodwork" in t for t in image_tags)

                if matches:
                    cname = None
                    try:
                        cname = container.name
                    except Exception:
                        cname = "<unknown>"
                    log.info("Stopping container %s...", cname)
                    try:
                        container.stop()
                    except Exception:
                        log.debug("Container %s may already be stopped.", cname)
                    log.info("Removing container %s...", cname)
                    try:
                        container.remove(force=True)
                    except Exception as e:
                        log.warning("Failed to remove container %s: %s", cname, e)
            except Exception as e:
                log.debug("Skipping container due to error: %s", e)
    except APIError as e:
        log.debug("Docker API error listing containers: %s", e)

    # Remove images with 'woodwork' in tag
    try:
        for image in client.images.list():
            try:
                tags = image.tags or []
                if any("woodwork" in t for t in tags):
                    for t in tags:
                        log.info("Removing image tag %s...", t)
                        try:
                            client.images.remove(t, force=True)
                        except Exception as e:
                            log.warning("Failed to remove image %s: %s", t, e)
            except Exception as e:
                log.debug("Skipping image due to error: %s", e)
    except APIError as e:
        log.debug("Docker API error listing images: %s", e)


def clean_all(root_path: pathlib.Path | None = None) -> None:
    """Perform a conservative cleanup for Woodwork.

    - Remove the .woodwork directory under `root_path` (defaults to current working dir)
    - Attempt to stop/remove containers and images that contain 'woodwork' in their name/tag

    This function does not try to be aggressive; it only removes items that clearly
    appear to be managed by Woodwork (based on the substring 'woodwork').
    """
    if root_path is None:
        root_path = pathlib.Path.cwd()

    ww_dir = root_path / ".woodwork"
    log.info("Running Woodwork cleanup. Target directory: %s", ww_dir)

    _rm_tree(ww_dir)

    # try docker cleanup
    _cleanup_docker()
