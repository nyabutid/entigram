import sys
import os
from .parser import SchemaParser
from .compiler import SchemaCompiler
from entigram.ontology_compiler.compiler import OntologyCompiler

def compile_schema_file(file_path: str, output_format: str = "sql", enable_crsqlite: bool = False) -> str:
    """
    Reads a Schema file, parses it, and compiles it into the requested format (sql, ttl, or mermaid).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Schema file not found: {file_path}")
        
    with open(file_path, 'r') as f:
        text = f.read()
    
    parser = SchemaParser(text)
    entities, relationships = parser.parse()
    
    if output_format.lower() == "ttl":
        compiler = OntologyCompiler(entities, relationships)
        return compiler.compile()
    elif output_format.lower() == "mermaid":
        from .graph_builder import SchemaGraphBuilder
        builder = SchemaGraphBuilder(entities, relationships)
        return builder.to_mermaid()
    else:
        compiler = SchemaCompiler(entities, relationships)
        return compiler.compile(enable_crsqlite=enable_crsqlite)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Entigram Schema Compiler")
    parser.add_argument("file", help="Path to the Schema file (.lds)")
    parser.add_argument("--format", choices=["sql", "ttl", "mermaid"], default="sql", help="Output format (default: sql)")

    
    args = parser.parse_args()
    
    try:
        print(compile_schema_file(args.file, args.format))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
