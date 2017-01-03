import ast
from sherlock.errors import CompileError, SyntaxNotSupportError, ParamTypeMismatchError
from sherlock.codelib.generator import CodeGenerator
from sherlock.codelib.analyzer.variable import Type, Variable, Variables
from sherlock.codelib.analyzer.function import Function, Functions


class CodeAnalyzer(object):
    def __init__(self, code):
        self.code = code
        self.module_node = ast.parse(self.code)
        self.functions = Functions()
        self.variables = Variables()
        if not isinstance(self.module_node, ast.Module):
            raise CompileError()

    def analysis(self):
        for node in self.module_node.body:
            if isinstance(node, ast.Assign):
                self.analysis_assign_node(self.variables, node)
            elif isinstance(node, ast.Expr):
                if isinstance(node.value, ast.Call):
                    self.get_type(node.value)
        generator = CodeGenerator(self.code, functions=self.functions, variables=self.variables)
        return generator

    def analysis_function(self, function_node, arg_types=[]):
        variables = Variables()
        return_type = Type.VOID

        for node in function_node.body:
            if isinstance(node, ast.Assign):
                self.analysis_assign_node(variables, node)
            elif isinstance(node, ast.Return):
                return_type = self.get_type(node.value)
                if return_type is None:
                    return_type = Type.VOID
        generator = CodeGenerator(self.code,variables=variables)
        return generator, return_type

    def analysis_assign_node(self, variables, node):
        if len(node.targets) > 1:
            raise SyntaxNotSupportError('Tuple assignment is not support yet.')
        target = node.targets[0]
        variables.append(Variable(name=target.id, var_type=self.get_type(node.value)))

    def get_function_return_type(self, function_name, arg_types=[]):
        function = self.functions[function_name]
        if function is not None:
            if function.is_arg_types_match(arg_types):
                return function.return_type
            else:
                raise ParamTypeMismatchError("Function '%s' parameter type is not match", function_name)
        else:
            for node in self.module_node.body:
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    generator, return_type = self.analysis_function(node, arg_types)
                self.functions.append(Function(function_name, arg_types, return_type, generator))

            return return_type

    def get_type(self, node):
        if isinstance(node, ast.BinOp):
            left_type = self.get_type(node.left)
            right_type = self.get_type(node.right)

            if isinstance(node.op, ast.Add):
                if left_type.is_number and right_type.is_number:
                    return Type.NUMBER
                else:
                    return Type.STRING
            elif left_type.is_number and right_type.is_number:
                return Type.NUMBER
            else:
                raise CompileError("Can not '%s' operator with string." % node.op.__class__.__name__)
        elif isinstance(node, ast.UnaryOp):
            if isinstance(operand, ast.Num):
                return Type.NUMBER
            else:
                raise SyntaxNotSupportError("Not support unary operator except number.")

        elif isinstance(node, ast.Num):
            return Type.NUMBER

        elif isinstance(node, ast.Str):
            return Type.STRING
        elif isinstance(node, ast.Call):
            arg_types = [self.get_type(arg) for arg in node.args]
            return self.get_function_return_type(node.func.id, arg_types)
        elif isinstance(node, ast.Name):
            return self.variables[node.id].var_type
