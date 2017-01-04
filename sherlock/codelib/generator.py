import ast
import types
from sherlock.errors import CompileError, SyntaxNotSupportError
from sherlock.codelib.analyzer.variable import Variables, Type
from sherlock.codelib.analyzer.function import Functions


CONTEXT_STATUS_GLOBAL = 1
CONTEXT_STATUS_FUNCTION = 2


class TempVariableManager(object):

    def __init__(self, prefix_name):
        self.prefix_name = prefix_name
        self.variable_id = 0

    def get_new_name(self):
        self.variable_id += 1
        return self.get_last_variable_name()

    def get_last_variable_name(self):
        return '%s_%d' % (self.prefix_name, self.variable_id)

class CodeGenerator(object):

    def __init__(
        self,
        code=None,
        node=None,
        context_status=CONTEXT_STATUS_GLOBAL,
        functions=Functions(),
        variables=Variables()
    ):
        self.context_status = context_status
        self.global_generator = None
        self.functions = functions
        self.code = code
        self.node = node
        self.variables = variables
        self.temp_variable = TempVariableManager('_return_data')

    @property
    def is_global(self):
        return self.context_status == CONTEXT_STATUS_GLOBAL

    def generate_assign(self, node):
        target_code = ''
        if isinstance(node.targets[0], ast.Name):
            target_code = self._generate(node.targets[0])
        else:
            raise CompileError()

        if isinstance(node.value, ast.Call):
            from sherlock.codelib import str_ast_node
            return '%s\n%s=$__return_%s' % (self._generate(node.value), target_code, node.value.func.id)
        else:
            value_code = self._generate(node.value)
            if value_code is None:
                raise CompileError()
            return target_code + '=' + value_code

    def generate_name(self, node):
        if isinstance(node.ctx, ast.Store) or isinstance(node.ctx, ast.Param):
            return 'export ' + node.id if self.is_global else 'local ' + node.id
        else:
            return '$' + node.id

    def generate(self):
        if self.node is None:
            self.node = ast.parse(self.code)
        if isinstance(self.node, ast.Module):
            return '\n'.join([self._generate(x) for x in self.node.body])
        elif isinstance(self.node, ast.FunctionDef):
            if not len(self.node.decorator_list) == 0:
                raise SyntaxNotSupportError('Function decoration is not support yet.')

            arguments_code = '\n'.join(['%s=$%i' % (self._generate(x), i + 1) for i, x in enumerate(self.node.args.args)])
            body_code = '\n'.join([self._generate(x, {'func_name': self.node.name}) for x in self.node.body])
            return 'function %s() {\n%s\n%s\n}' % (self.node.name, arguments_code, body_code)
        else:
            raise CompileError()

    def generate_expr(self, node):
        # line comment
        if isinstance(node.value, ast.Str):
            return ''
        else:
            return self._generate(node.value)

    def generate_call(self, node):
        if hasattr(node, 'kwargs'):
            if not node.kwargs is None:
                raise SyntaxNotSupportError('Keyword arguments is not support yet.')
        elif not len(node.keywords) == 0:
            raise SyntaxNotSupportError('Keyword arguments is not support yet.')
        funciton_name = node.func.id
        arguments_code = ' '.join([self._generate(x) for x in node.args])
        return '%s %s' % (funciton_name, arguments_code)

    def generate_binop(self, node):
        left_type = self.get_type(node.left)
        right_type = self.get_type(node.right)
        print(left_type)
        if left_type.is_number and right_type.is_number:
            op = ''
            if isinstance(node.op, ast.Add):
                op = '+'
            elif isinstance(node.op, ast.Sub):
                op = '-'
            elif isinstance(node.op, ast.Mult):
                op = '*'
            elif isinstance(node.op, ast.Div):
                op = '/'
            else:
                raise SyntaxNotSupportError("%s operation is not support yet." % node.op.__class__.__name__)
            return '$(( %s %s %s ))' % (self._generate(node.left), op, self._generate(node.right))
        elif (left_type.is_string or right_type.is_string) and isinstance(node.op, ast.Add):
            return self._generate(node.left) + self._generate(node.right)
        else:
            raise SyntaxNotSupportError("%s operation is not support yet." % node.op.__class__.__name__)

    def _generate(self, node, ext_info={}):
        if isinstance(node, ast.Assign):
            return self.generate_assign(node)
        elif isinstance(node, ast.Name):
            return self.generate_name(node)
        elif isinstance(node, ast.Expr):
            return self.generate_expr(node)
        elif isinstance(node, ast.Call):
            return self.generate_call(node)
        elif isinstance(node, ast.Num):
            return str(node.n)
        elif isinstance(node, ast.BinOp):
            return self.generate_binop(node)
        elif isinstance(node, ast.Str):
            return '"' + node.s.replace('"','\\"') + '"'
        elif isinstance(node, ast.FunctionDef):
            generator = CodeGenerator(node=node, context_status=CONTEXT_STATUS_FUNCTION)
            return generator.generate()
        elif hasattr(ast, 'arg') and isinstance(node, ast.arg):
            return 'local ' + node.arg
        elif isinstance(node, ast.Return):
            return 'export __return_%s=%s' % (ext_info['func_name'], self._generate(node.value))
        else:
            raise SyntaxNotSupportError("%s is not support yet." % node.__class__.__name__)

    def get_type(self, node):
        if isinstance(node, ast.Num):
            return Type.NUMBER
        elif isinstance(node, ast.Str):
            return Type.STRING
        elif isinstance(node, ast.Name):
            return self.variables[node.id].var_type
        elif isinstance(node, ast.BinOp):
            if self.get_type(node.left).is_number and self.get_type(node.right).is_number:
                return Type.NUMBER
            elif self.get_type(node.left).is_string or self.get_type(node.right).is_string:
                return Type.STRING
        else:
            return Type.VOID
