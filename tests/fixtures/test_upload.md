# Test Upload Documentation

This is a test file to verify the upload functionality works correctly.

## Python Example

Here's a simple Python function:

```python
def hello_world(name: str) -> str:
    """
    Greet someone by name.
    
    Args:
        name: The person's name
        
    Returns:
        A greeting message
    """
    return f"Hello, {name}!"
```

## JavaScript Example

And here's the same function in JavaScript:

```javascript
/**
 * Greet someone by name
 * @param {string} name - The person's name
 * @returns {string} A greeting message
 */
function helloWorld(name) {
    return `Hello, ${name}!`;
}
```

## Configuration Example

Here's a YAML configuration example:

```yaml
server:
  host: localhost
  port: 8080
  debug: true

database:
  url: postgresql://localhost/myapp
  pool_size: 10
```

## Indented Code Block

    # This is an indented code block
    # It should also be detected
    def indented_example():
        print("This uses 4-space indentation")
        return True

## Conclusion

This test file contains various types of code blocks to test extraction.