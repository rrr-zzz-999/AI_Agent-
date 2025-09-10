"""
Code Sanitizer Tool
代码清理工具

该工具消除非必要元素，包括注释、未使用的代码和无关的库依赖项，
使代理能够专注于分析可执行逻辑，避免潜在误导性文档的危险。
"""

import re
import json
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import ast
import solcx
from slither import Slither
from slither.core.declarations import Contract, Function


@dataclass
class SanitizedCode:
    """清理后的代码"""
    original_code: str
    sanitized_code: str
    removed_comments: List[str]
    removed_functions: List[str]
    removed_imports: List[str]
    removed_variables: List[str]
    optimization_summary: Dict[str, int]


@dataclass
class CodeAnalysis:
    """代码分析结果"""
    functions: Set[str]
    variables: Set[str]
    imports: Set[str]
    comments: List[str]
    used_functions: Set[str]
    used_variables: Set[str]
    dependencies: Set[str]


class CodeSanitizerTool:
    """代码清理工具"""
    
    def __init__(self):
        """初始化代码清理工具"""
        self.solidity_keywords = {
            'pragma', 'contract', 'interface', 'library', 'function', 'modifier',
            'event', 'struct', 'enum', 'mapping', 'address', 'uint', 'int',
            'bool', 'bytes', 'string', 'public', 'private', 'internal', 'external',
            'view', 'pure', 'payable', 'constant', 'immutable', 'override',
            'virtual', 'abstract', 'if', 'else', 'for', 'while', 'do', 'break',
            'continue', 'return', 'require', 'assert', 'revert', 'emit', 'new',
            'delete', 'try', 'catch', 'assembly', 'storage', 'memory', 'calldata'
        }
    
    def sanitize_solidity_code(self, source_code: str, keep_essential_comments: bool = True) -> SanitizedCode:
        """
        清理Solidity源代码
        
        Args:
            source_code: 原始源代码
            keep_essential_comments: 是否保留重要注释（如NatSpec）
            
        Returns:
            清理后的代码对象
        """
        # 分析代码结构
        analysis = self._analyze_solidity_code(source_code)
        
        # 执行清理步骤
        sanitized = source_code
        removed_comments = []
        removed_functions = []
        removed_imports = []
        removed_variables = []
        
        # 1. 移除注释
        sanitized, comments = self._remove_comments(sanitized, keep_essential_comments)
        removed_comments.extend(comments)
        
        # 2. 移除未使用的导入
        sanitized, imports = self._remove_unused_imports(sanitized, analysis)
        removed_imports.extend(imports)
        
        # 3. 移除未使用的函数
        sanitized, functions = self._remove_unused_functions(sanitized, analysis)
        removed_functions.extend(functions)
        
        # 4. 移除未使用的变量
        sanitized, variables = self._remove_unused_variables(sanitized, analysis)
        removed_variables.extend(variables)
        
        # 5. 清理空行和多余空格
        sanitized = self._clean_whitespace(sanitized)
        
        # 6. 移除调试代码
        sanitized = self._remove_debug_code(sanitized)
        
        # 生成优化摘要
        optimization_summary = {
            "removed_comments": len(removed_comments),
            "removed_functions": len(removed_functions),
            "removed_imports": len(removed_imports),
            "removed_variables": len(removed_variables),
            "size_reduction": len(source_code) - len(sanitized),
            "size_reduction_percent": round((len(source_code) - len(sanitized)) / len(source_code) * 100, 2)
        }
        
        return SanitizedCode(
            original_code=source_code,
            sanitized_code=sanitized,
            removed_comments=removed_comments,
            removed_functions=removed_functions,
            removed_imports=removed_imports,
            removed_variables=removed_variables,
            optimization_summary=optimization_summary
        )
    
    def _analyze_solidity_code(self, source_code: str) -> CodeAnalysis:
        """
        分析Solidity代码结构
        
        Args:
            source_code: 源代码
            
        Returns:
            代码分析结果
        """
        functions = set()
        variables = set()
        imports = set()
        comments = []
        used_functions = set()
        used_variables = set()
        dependencies = set()
        
        lines = source_code.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # 提取注释
            if line.startswith('//') or line.startswith('/*') or '*/' in line:
                comments.append(line)
            
            # 提取导入
            if line.startswith('import'):
                match = re.search(r'import\s+["\']([^"\']+)["\']', line)
                if match:
                    imports.add(match.group(1))
            
            # 提取函数定义
            func_match = re.search(r'function\s+(\w+)\s*\(', line)
            if func_match:
                functions.add(func_match.group(1))
            
            # 提取变量定义
            var_matches = re.findall(r'(?:uint256|uint|int|address|bool|bytes32|string)\s+(\w+)', line)
            for var in var_matches:
                if var not in self.solidity_keywords:
                    variables.add(var)
            
            # 查找函数调用
            call_matches = re.findall(r'(\w+)\s*\(', line)
            for call in call_matches:
                if call in functions:
                    used_functions.add(call)
            
            # 查找变量使用
            for var in variables:
                if var in line and not line.strip().startswith('//'):
                    used_variables.add(var)
        
        return CodeAnalysis(
            functions=functions,
            variables=variables,
            imports=imports,
            comments=comments,
            used_functions=used_functions,
            used_variables=used_variables,
            dependencies=dependencies
        )
    
    def _remove_comments(self, code: str, keep_essential: bool = True) -> Tuple[str, List[str]]:
        """
        移除注释
        
        Args:
            code: 源代码
            keep_essential: 是否保留重要注释
            
        Returns:
            (清理后的代码, 移除的注释列表)
        """
        removed_comments = []
        lines = code.split('\n')
        cleaned_lines = []
        in_block_comment = False
        
        for line in lines:
            original_line = line
            
            # 处理块注释
            if '/*' in line and '*/' in line:
                # 单行块注释
                comment_start = line.find('/*')
                comment_end = line.find('*/') + 2
                comment = line[comment_start:comment_end]
                
                # 检查是否为重要注释
                if keep_essential and self._is_essential_comment(comment):
                    cleaned_lines.append(line)
                else:
                    removed_comments.append(comment)
                    line = line[:comment_start] + line[comment_end:]
                    cleaned_lines.append(line)
            elif '/*' in line:
                # 块注释开始
                in_block_comment = True
                comment_start = line.find('/*')
                comment = line[comment_start:]
                removed_comments.append(comment)
                line = line[:comment_start]
                cleaned_lines.append(line)
            elif '*/' in line and in_block_comment:
                # 块注释结束
                in_block_comment = False
                comment_end = line.find('*/') + 2
                comment = line[:comment_end]
                removed_comments.append(comment)
                line = line[comment_end:]
                cleaned_lines.append(line)
            elif in_block_comment:
                # 在块注释中
                removed_comments.append(line)
                continue
            elif line.strip().startswith('//'):
                # 单行注释
                if keep_essential and self._is_essential_comment(line):
                    cleaned_lines.append(line)
                else:
                    removed_comments.append(line.strip())
                    # 如果行内有代码，只移除注释部分
                    comment_start = line.find('//')
                    if comment_start > 0 and line[:comment_start].strip():
                        cleaned_lines.append(line[:comment_start].rstrip())
            else:
                # 处理行内注释
                comment_pos = line.find('//')
                if comment_pos > 0:
                    comment = line[comment_pos:]
                    if keep_essential and self._is_essential_comment(comment):
                        cleaned_lines.append(line)
                    else:
                        removed_comments.append(comment)
                        cleaned_lines.append(line[:comment_pos].rstrip())
                else:
                    cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines), removed_comments
    
    def _is_essential_comment(self, comment: str) -> bool:
        """
        判断是否为重要注释
        
        Args:
            comment: 注释内容
            
        Returns:
            是否为重要注释
        """
        essential_patterns = [
            r'@dev\s+',  # NatSpec开发者注释
            r'@param\s+',  # NatSpec参数注释
            r'@return\s+',  # NatSpec返回值注释
            r'@notice\s+',  # NatSpec用户注释
            r'SPDX-License-Identifier',  # 许可证标识
            r'pragma\s+',  # 编译指令
            r'TODO',  # 待办事项
            r'FIXME',  # 修复标记
            r'WARNING',  # 警告
            r'SECURITY',  # 安全注释
            r'@audit',  # 审计标记
        ]
        
        for pattern in essential_patterns:
            if re.search(pattern, comment, re.IGNORECASE):
                return True
        
        return False
    
    def _remove_unused_imports(self, code: str, analysis: CodeAnalysis) -> Tuple[str, List[str]]:
        """
        移除未使用的导入
        
        Args:
            code: 源代码
            analysis: 代码分析结果
            
        Returns:
            (清理后的代码, 移除的导入列表)
        """
        removed_imports = []
        lines = code.split('\n')
        cleaned_lines = []
        
        for line in lines:
            if line.strip().startswith('import'):
                # 检查导入是否被使用
                import_match = re.search(r'import\s+["\']([^"\']+)["\']', line)
                if import_match:
                    import_path = import_match.group(1)
                    
                    # 简单的使用检查（可以扩展为更复杂的分析）
                    import_name = Path(import_path).stem
                    if self._is_import_used(code, import_name, import_path):
                        cleaned_lines.append(line)
                    else:
                        removed_imports.append(line.strip())
                else:
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines), removed_imports
    
    def _is_import_used(self, code: str, import_name: str, import_path: str) -> bool:
        """
        检查导入是否被使用
        
        Args:
            code: 源代码
            import_name: 导入名称
            import_path: 导入路径
            
        Returns:
            是否被使用
        """
        # 检查是否有对导入库的引用
        patterns = [
            rf'\b{import_name}\.',  # 直接使用库名
            rf'using\s+{import_name}',  # using声明
            rf'import.*{import_name}',  # 其他导入形式
        ]
        
        for pattern in patterns:
            if re.search(pattern, code):
                return True
        
        return False
    
    def _remove_unused_functions(self, code: str, analysis: CodeAnalysis) -> Tuple[str, List[str]]:
        """
        移除未使用的函数
        
        Args:
            code: 源代码
            analysis: 代码分析结果
            
        Returns:
            (清理后的代码, 移除的函数列表)
        """
        removed_functions = []
        
        # 识别未使用的私有/内部函数
        unused_functions = analysis.functions - analysis.used_functions
        
        # 过滤掉公共函数和特殊函数
        truly_unused = set()
        for func in unused_functions:
            if not self._is_special_function(func) and self._is_private_or_internal_function(code, func):
                truly_unused.add(func)
        
        # 移除未使用的函数
        cleaned_code = code
        for func_name in truly_unused:
            func_pattern = rf'function\s+{func_name}\s*\([^{{]*\{{[^}}]*\}}'
            matches = re.finditer(func_pattern, cleaned_code, re.DOTALL)
            
            for match in matches:
                removed_functions.append(f"function {func_name}")
                cleaned_code = cleaned_code.replace(match.group(0), '')
        
        return cleaned_code, removed_functions
    
    def _is_special_function(self, func_name: str) -> bool:
        """
        检查是否为特殊函数
        
        Args:
            func_name: 函数名
            
        Returns:
            是否为特殊函数
        """
        special_functions = {
            'constructor', 'receive', 'fallback', 'initialize',
            'onlyOwner', 'whenNotPaused', 'nonReentrant'
        }
        
        return func_name in special_functions or func_name.startswith('_')
    
    def _is_private_or_internal_function(self, code: str, func_name: str) -> bool:
        """
        检查函数是否为私有或内部函数
        
        Args:
            code: 源代码
            func_name: 函数名
            
        Returns:
            是否为私有或内部函数
        """
        func_pattern = rf'function\s+{func_name}\s*\([^{{]*'
        match = re.search(func_pattern, code)
        
        if match:
            func_declaration = match.group(0)
            return 'private' in func_declaration or 'internal' in func_declaration
        
        return False
    
    def _remove_unused_variables(self, code: str, analysis: CodeAnalysis) -> Tuple[str, List[str]]:
        """
        移除未使用的变量
        
        Args:
            code: 源代码
            analysis: 代码分析结果
            
        Returns:
            (清理后的代码, 移除的变量列表)
        """
        removed_variables = []
        unused_variables = analysis.variables - analysis.used_variables
        
        cleaned_code = code
        for var_name in unused_variables:
            # 移除未使用的局部变量声明
            var_patterns = [
                rf'uint256\s+{var_name}\s*;',
                rf'uint\s+{var_name}\s*;',
                rf'int\s+{var_name}\s*;',
                rf'address\s+{var_name}\s*;',
                rf'bool\s+{var_name}\s*;',
                rf'bytes32\s+{var_name}\s*;',
                rf'string\s+{var_name}\s*;'
            ]
            
            for pattern in var_patterns:
                if re.search(pattern, cleaned_code):
                    cleaned_code = re.sub(pattern, '', cleaned_code)
                    removed_variables.append(var_name)
        
        return cleaned_code, removed_variables
    
    def _clean_whitespace(self, code: str) -> str:
        """
        清理多余的空格和空行
        
        Args:
            code: 源代码
            
        Returns:
            清理后的代码
        """
        lines = code.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # 移除行尾空格
            line = line.rstrip()
            cleaned_lines.append(line)
        
        # 移除多余的连续空行
        final_lines = []
        prev_empty = False
        
        for line in cleaned_lines:
            if line.strip() == '':
                if not prev_empty:
                    final_lines.append(line)
                prev_empty = True
            else:
                final_lines.append(line)
                prev_empty = False
        
        return '\n'.join(final_lines)
    
    def _remove_debug_code(self, code: str) -> str:
        """
        移除调试代码
        
        Args:
            code: 源代码
            
        Returns:
            清理后的代码
        """
        # 移除console.log等调试语句
        debug_patterns = [
            r'console\.log\([^)]*\);\s*',
            r'console\.error\([^)]*\);\s*',
            r'console\.warn\([^)]*\);\s*',
            r'require\(false,\s*[^)]*\);\s*',  # 调试用的require
            r'assert\(false[^)]*\);\s*',  # 调试用的assert
        ]
        
        cleaned_code = code
        for pattern in debug_patterns:
            cleaned_code = re.sub(pattern, '', cleaned_code, flags=re.MULTILINE)
        
        return cleaned_code
    
    def sanitize_multiple_files(self, file_paths: List[str]) -> Dict[str, SanitizedCode]:
        """
        批量清理多个文件
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            文件路径到清理结果的映射
        """
        results = {}
        
        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
                
                sanitized = self.sanitize_solidity_code(source_code)
                results[file_path] = sanitized
                
            except Exception as e:
                print(f"处理文件 {file_path} 时出错: {e}")
        
        return results
    
    def analyze_optimization_impact(self, sanitized: SanitizedCode) -> Dict[str, Any]:
        """
        分析优化影响
        
        Args:
            sanitized: 清理结果
            
        Returns:
            优化影响分析
        """
        return {
            "size_reduction": {
                "bytes": sanitized.optimization_summary["size_reduction"],
                "percentage": sanitized.optimization_summary["size_reduction_percent"]
            },
            "removed_elements": {
                "comments": sanitized.optimization_summary["removed_comments"],
                "functions": sanitized.optimization_summary["removed_functions"],
                "imports": sanitized.optimization_summary["removed_imports"],
                "variables": sanitized.optimization_summary["removed_variables"]
            },
            "readability_impact": self._assess_readability_impact(sanitized),
            "maintainability_impact": self._assess_maintainability_impact(sanitized)
        }
    
    def _assess_readability_impact(self, sanitized: SanitizedCode) -> str:
        """
        评估可读性影响
        
        Args:
            sanitized: 清理结果
            
        Returns:
            可读性影响评估
        """
        if sanitized.optimization_summary["removed_comments"] > 20:
            return "显著降低 - 移除了大量注释"
        elif sanitized.optimization_summary["removed_comments"] > 5:
            return "轻微降低 - 移除了一些注释"
        else:
            return "基本无影响"
    
    def _assess_maintainability_impact(self, sanitized: SanitizedCode) -> str:
        """
        评估可维护性影响
        
        Args:
            sanitized: 清理结果
            
        Returns:
            可维护性影响评估
        """
        total_removed = (sanitized.optimization_summary["removed_functions"] + 
                        sanitized.optimization_summary["removed_variables"])
        
        if total_removed > 10:
            return "积极影响 - 移除了大量无用代码"
        elif total_removed > 3:
            return "轻微积极影响 - 清理了一些无用代码"
        else:
            return "基本无影响"
    
    def generate_sanitization_report(self, sanitized: SanitizedCode) -> str:
        """
        生成清理报告
        
        Args:
            sanitized: 清理结果
            
        Returns:
            清理报告
        """
        report_lines = []
        report_lines.append("=== 代码清理报告 ===")
        report_lines.append("")
        
        # 基本统计
        report_lines.append("基本统计:")
        report_lines.append(f"  原始代码大小: {len(sanitized.original_code):,} 字节")
        report_lines.append(f"  清理后大小: {len(sanitized.sanitized_code):,} 字节")
        report_lines.append(f"  减少大小: {sanitized.optimization_summary['size_reduction']:,} 字节 ({sanitized.optimization_summary['size_reduction_percent']}%)")
        report_lines.append("")
        
        # 移除的元素
        report_lines.append("移除的元素:")
        report_lines.append(f"  注释: {sanitized.optimization_summary['removed_comments']} 个")
        report_lines.append(f"  函数: {sanitized.optimization_summary['removed_functions']} 个")
        report_lines.append(f"  导入: {sanitized.optimization_summary['removed_imports']} 个")
        report_lines.append(f"  变量: {sanitized.optimization_summary['removed_variables']} 个")
        report_lines.append("")
        
        # 详细列表
        if sanitized.removed_functions:
            report_lines.append("移除的函数:")
            for func in sanitized.removed_functions:
                report_lines.append(f"  - {func}")
            report_lines.append("")
        
        if sanitized.removed_imports:
            report_lines.append("移除的导入:")
            for imp in sanitized.removed_imports:
                report_lines.append(f"  - {imp}")
            report_lines.append("")
        
        # 影响分析
        impact = self.analyze_optimization_impact(sanitized)
        report_lines.append("影响分析:")
        report_lines.append(f"  可读性影响: {impact['readability_impact']}")
        report_lines.append(f"  可维护性影响: {impact['maintainability_impact']}")
        
        return "\n".join(report_lines)


# 使用示例
def main():
    """使用示例"""
    # 初始化工具
    sanitizer = CodeSanitizerTool()
    
    # 示例Solidity代码
    sample_code = '''
    // SPDX-License-Identifier: MIT
    pragma solidity ^0.8.0;
    
    import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
    import "./UnusedContract.sol";  // 这个导入未被使用
    
    /**
     * @title Sample Contract
     * @dev This is a sample contract for demonstration
     */
    contract SampleContract is ERC20 {
        // 状态变量
        uint256 public totalSupply;
        address private owner;
        uint256 private unusedVariable;  // 未使用的变量
        
        // 构造函数
        constructor() ERC20("Sample", "SMPL") {
            owner = msg.sender;
            totalSupply = 1000000 * 10**18;
        }
        
        // 公共函数
        function getOwner() public view returns (address) {
            return owner;
        }
        
        // 未使用的私有函数
        function _unusedFunction() private pure returns (uint256) {
            return 42;
        }
        
        // 调试函数（应该被移除）
        function debugFunction() public {
            console.log("Debug message");
            require(false, "Debug require");
        }
    }
    '''
    
    # 清理代码
    result = sanitizer.sanitize_solidity_code(sample_code)
    
    # 生成报告
    report = sanitizer.generate_sanitization_report(result)
    print(report)
    print("\n" + "="*50 + "\n")
    print("清理后的代码:")
    print(result.sanitized_code)


if __name__ == "__main__":
    main()

