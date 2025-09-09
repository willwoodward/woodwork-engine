import logging
import pathlib
import shutil

log = logging.getLogger(__name__)


def _rm_tree(path: pathlib.Path) -> None:
    """Recursively remove a directory if it exists.
    
    Since Docker containers now run as the current user, files should be 
    owned by the current user and removable without special permissions.
    """
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
        log.warning("If files are owned by root (from old containers), run: sudo rm -rf %s", path)


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
        import time
    except Exception as e:
        log.debug("Docker SDK not available or failed to import: %s", e)
        return

    try:
        client = docker.from_env()
    except Exception as e:
        log.debug("Could not initialise Docker client: %s", e)
        return

    containers_to_wait_for = []

    # Stop containers whose image tags include 'woodwork'
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
                    
                    # Check if container is running
                    try:
                        if container.status == 'running':
                            log.info("Stopping container %s...", cname)
                            container.stop(timeout=10)  # Give it 10 seconds to stop gracefully
                            containers_to_wait_for.append((container, cname))
                        else:
                            log.debug("Container %s is already stopped", cname)
                    except Exception as e:
                        log.debug("Error stopping container %s: %s", cname, e)
            except Exception as e:
                log.debug("Skipping container due to error: %s", e)
    except APIError as e:
        log.debug("Docker API error listing containers: %s", e)

    # Wait for containers to actually stop
    if containers_to_wait_for:
        log.info("Waiting for containers to stop...")
        max_wait_time = 30  # Maximum time to wait in seconds
        start_time = time.time()
        
        while containers_to_wait_for and (time.time() - start_time) < max_wait_time:
            containers_still_running = []
            for container, cname in containers_to_wait_for:
                try:
                    container.reload()
                    if container.status != 'exited':
                        containers_still_running.append((container, cname))
                    else:
                        log.debug("Container %s has stopped", cname)
                except Exception:
                    # If we can't check status, assume it's stopped
                    pass
            
            containers_to_wait_for = containers_still_running
            if containers_to_wait_for:
                time.sleep(1)
        
        # Force stop any remaining containers
        for container, cname in containers_to_wait_for:
            log.warning("Force stopping container %s (didn't stop gracefully)", cname)
            try:
                container.kill()
            except Exception as e:
                log.debug("Error force stopping %s: %s", cname, e)

    # Now remove all woodwork containers
    try:
        for container in client.containers.list(all=True):
            try:
                image_tags = []
                try:
                    image_tags = container.image.tags or []
                except Exception:
                    pass

                matches = any("woodwork" in t for t in image_tags)
                if matches:
                    cname = container.name if hasattr(container, 'name') else "<unknown>"
                    log.info("Removing container %s...", cname)
                    try:
                        container.remove(force=True)
                    except Exception as e:
                        log.warning("Failed to remove container %s: %s", cname, e)
            except Exception as e:
                log.debug("Skipping container due to error: %s", e)
    except APIError as e:
        log.debug("Docker API error removing containers: %s", e)

    # Remove volumes with 'woodwork' in name
    try:
        volumes = client.volumes.list()
        for volume in volumes:
            try:
                volume_name = volume.name
                if "woodwork" in volume_name.lower():
                    log.info("Removing volume %s...", volume_name)
                    try:
                        volume.remove(force=True)
                    except Exception as e:
                        log.warning("Failed to remove volume %s: %s", volume_name, e)
            except Exception as e:
                log.debug("Skipping volume due to error: %s", e)
    except APIError as e:
        log.debug("Docker API error listing volumes: %s", e)

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

    # Clean up any dangling volumes
    try:
        log.info("Pruning unused volumes...")
        client.volumes.prune()
    except Exception as e:
        log.debug("Error pruning volumes: %s", e)


def clean_all(root_path: pathlib.Path | None = None) -> None:
    """Perform a conservative cleanup for Woodwork.

    - Stop/remove Docker containers, volumes, and images with 'woodwork'
    - Remove the .woodwork directory under `root_path` (defaults to current working dir)

    This function only removes items that clearly appear to be managed by Woodwork.
    """
    if root_path is None:
        root_path = pathlib.Path.cwd()

    ww_dir = root_path / ".woodwork"
    log.info("Running Woodwork cleanup for: %s", ww_dir)

    # Clean up Docker resources FIRST
    log.info("Cleaning up Docker containers, volumes, and images...")
    _cleanup_docker()
    
    # Remove the .woodwork directory
    log.info("Removing .woodwork directory...")
    _rm_tree(ww_dir)
    
    # Verify cleanup
    if ww_dir.exists():
        log.warning("Directory still exists after cleanup: %s", ww_dir)
        log.warning("This may be due to old root-owned files. Try: sudo rm -rf %s", ww_dir)
    else:
        log.info("Cleanup completed successfully")
