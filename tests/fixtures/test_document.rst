==================
RST Test Document
==================

This is a test RST document with various code block formats.

Introduction
============

This document contains different types of code blocks for testing extraction.

Code Block Directive
--------------------

Here's a Python example using the code-block directive:

.. code-block:: python

    def fibonacci(n):
        """Calculate the nth Fibonacci number."""
        if n <= 1:
            return n
        return fibonacci(n - 1) + fibonacci(n - 2)

    # Example usage
    for i in range(10):
        print(f"F({i}) = {fibonacci(i)}")

Code Directive
--------------

JavaScript example using the shorter code directive:

.. code:: javascript

    const greet = (name) => {
        console.log(`Hello, ${name}!`);
    };
    
    greet("World");

Sourcecode Directive
--------------------

SQL example using sourcecode:

.. sourcecode:: sql

    SELECT users.name, COUNT(orders.id) as order_count
    FROM users
    LEFT JOIN orders ON users.id = orders.user_id
    GROUP BY users.id, users.name
    HAVING COUNT(orders.id) > 5
    ORDER BY order_count DESC;

Literal Blocks
--------------

Here's a literal block using double colons::

    This is a literal block
    It preserves all    spacing
    And special characters: @#$%^&*()
    
    Even blank lines are preserved

Another way to create literal blocks::

    $ pip install codedox
    $ codedox init
    $ codedox search "authentication"

Code with Options
-----------------

Code block with various options:

.. code-block:: python
   :linenos:
   :caption: Advanced Example
   :emphasize-lines: 3,4

    class DataProcessor:
        def __init__(self, data):
            self.data = data  # Important: store data
            self.processed = False  # Track processing state
        
        def process(self):
            if not self.processed:
                self.data = self._transform(self.data)
                self.processed = True
            return self.data

Multiple Languages
------------------

Here are examples in different languages:

.. code-block:: rust

    fn main() {
        let message = "Hello from Rust!";
        println!("{}", message);
    }

.. code-block:: go

    package main
    
    import "fmt"
    
    func main() {
        fmt.Println("Hello from Go!")
    }

.. code-block:: yaml

    apiVersion: v1
    kind: Service
    metadata:
      name: my-service
    spec:
      selector:
        app: MyApp
      ports:
        - protocol: TCP
          port: 80
          targetPort: 8080

Conclusion
==========

This document should provide good test coverage for RST code extraction.