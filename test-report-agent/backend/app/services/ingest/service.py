import pandas as pd
from typing import List, Dict, Any
import json
from app.core.logging import get_logger
from app.models.testcase import TestCase
from app.services.llm.client import llm_client
import uuid

logger = get_logger("ingest_service")

class IngestService:
    async def parse_excel(self, file_path: str, job_id: str) -> List[Dict[str, Any]]:
        logger.info(f"Parsing Excel file: {file_path}")
        try:
            # Read all sheets
            xls = pd.ExcelFile(file_path)
            all_cases = []
            
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # 1. LLM-based Column Alignment
                df = await self._align_columns_with_llm(df, sheet_name)
                
                # 2. LLM-based Result Normalization
                df = await self._normalize_results_with_llm(df)
                
                # Iterate rows
                for index, row in df.iterrows():
                    # Skip empty rows (must have case_name or result)
                    if pd.isna(row.get("case_name")) and pd.isna(row.get("test_result")):
                        continue
                        
                    case_data = self._row_to_case_dict(row, index, sheet_name, file_path, job_id)
                    all_cases.append(case_data)
            
            logger.info(f"Parsed {len(all_cases)} cases from {file_path}")
            return all_cases
            
        except Exception as e:
            logger.error(f"Failed to parse Excel: {e}")
            raise e

    async def _align_columns_with_llm(self, df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
        headers = df.columns.tolist()
        # Take first valid row as sample
        sample = {}
        if not df.empty:
            # Find a row that isn't all NaN
            for _, row in df.head(5).iterrows():
                if not row.isna().all():
                    sample = row.fillna("").to_dict()
                    break
        
        prompt = f"""
        你是一个数据解析引擎。你的任务是将输入的 Excel 列名映射到标准字段。
        
        【重要指令】
        1. 仅输出纯 JSON 字符串。
        2. 严禁输出任何 Python 代码、Markdown 标记（如 ```json）、解释或思考过程。
        3. 如果输出包含非 JSON 内容，任务将失败。
        
        标准字段说明：
        - case_name: 用例名称/标题 (必选)
        - precondition: 前置条件
        - steps: 测试步骤
        - expected: 预期结果
        - actual: 实际结果
        - test_result: 测试结果/状态 (必选)
        - priority: 优先级
        - executor: 执行人
        - remark: 备注
        
        输入数据：
        - 列名列表: {headers}
        - 样本数据: {sample}
        
        请返回 JSON 对象，键为表格中的原始列名，值为对应的标准字段名。
        
        示例输出：
        {{
            "测试标题": "case_name",
            "状态": "test_result"
        }}
        """
        
        try:
            logger.info(f"Aligning columns for sheet {sheet_name} with LLM...")
            mapping = await llm_client.achat_completion([{"role": "user", "content": prompt}], response_format=dict)
            
            if not isinstance(mapping, dict):
                 # Fallback parsing if LLM returns string
                logger.warning("LLM returned string instead of dict for column mapping, attempting parse")
                mapping = json.loads(str(mapping))

            logger.info(f"Column mapping received: {mapping}")
            
            # Clean mapping (remove keys not in headers)
            valid_mapping = {k: v for k, v in mapping.items() if k in headers}
            
            # Deduplicate values: Ensure one standard field maps to only one original column
            # We reverse the mapping to keep the last occurrence (or first, depending on iteration order).
            # To be safer, we can prioritize: if we have duplicates, we just pick one.
            reversed_map = {}
            for orig_col, std_col in valid_mapping.items():
                if std_col not in reversed_map:
                    reversed_map[std_col] = orig_col
                else:
                    logger.warning(f"Duplicate mapping for {std_col}: {reversed_map[std_col]} vs {orig_col}. Keeping {reversed_map[std_col]}")
            
            # Re-reverse to get the final mapping
            final_mapping = {v: k for k, v in reversed_map.items()}
            
            return df.rename(columns=final_mapping)
            
        except Exception as e:
            logger.error(f"Column alignment failed: {e}")
            # Fallback to empty mapping (will likely fail validation later, but better than crash)
            return df

    async def _normalize_results_with_llm(self, df: pd.DataFrame) -> pd.DataFrame:
        if "test_result" not in df.columns:
            logger.warning("'test_result' column not found after alignment.")
            return df
            
        unique_values = df["test_result"].dropna().astype(str).unique().tolist()
        if not unique_values:
            return df
            
        prompt = f"""
        请将以下测试结果值映射到标准状态：Pass, Fail, Blocked, Skipped。
        
        【重要指令】
        1. 仅输出纯 JSON 字符串。
        2. 严禁输出 Python 代码或 Markdown。
        
        输入值列表：{unique_values}
        
        规则：
        - 成功/通过/OK/Success -> Pass
        - 失败/错误/Fail/Error/Bug -> Fail
        - 阻塞/Block/Blocked -> Blocked
        - 跳过/不适用/Skip/NA -> Skipped
        
        示例输出：
        {{
            "通过": "Pass",
            "bug": "Fail"
        }}
        """
        
        try:
            logger.info(f"Normalizing results with LLM for values: {unique_values}")
            mapping = await llm_client.achat_completion([{"role": "user", "content": prompt}], response_format=dict)
            
            if not isinstance(mapping, dict):
                 mapping = json.loads(str(mapping))
                 
            logger.info(f"Result mapping received: {mapping}")
            
            # Apply mapping
            df["normalized_result"] = df["test_result"].astype(str).map(mapping).fillna("Skipped")
            return df
            
        except Exception as e:
            logger.error(f"Result normalization failed: {e}")
            df["normalized_result"] = "Skipped"
            return df

    def _row_to_case_dict(self, row: pd.Series, row_idx: int, sheet: str, file: str, job_id: str) -> Dict[str, Any]:
        # Basic fields
        case_dict = {
            "job_id": job_id,
            "case_name": str(row.get("case_name", "")).strip(),
            "precondition": str(row.get("precondition", "")).strip() if not pd.isna(row.get("precondition")) else None,
            "steps": str(row.get("steps", "")).strip() if not pd.isna(row.get("steps")) else None,
            "expected": str(row.get("expected", "")).strip() if not pd.isna(row.get("expected")) else None,
            "actual": str(row.get("actual", "")).strip() if not pd.isna(row.get("actual")) else None,
            "test_result": str(row.get("test_result", "")).strip(),
            "priority": str(row.get("priority", "")).strip() if not pd.isna(row.get("priority")) else None,
            "executor": str(row.get("executor", "")).strip() if not pd.isna(row.get("executor")) else None,
            "remark": str(row.get("remark", "")).strip() if not pd.isna(row.get("remark")) else None,
            "source_file": file,
            "source_sheet": sheet,
            "source_row": row_idx + 2, # 1-based + header
            "parse_warnings": []
        }
        
        # Result is already normalized in _normalize_results_with_llm, but if that failed or row has new value:
        if "normalized_result" in row:
             case_dict["normalized_result"] = row["normalized_result"]
        else:
             case_dict["normalized_result"] = "Skipped"
        
        # Validation checks
        if not case_dict["case_name"]:
            case_dict["parse_warnings"].append("Missing Case Name")
        if not case_dict["test_result"]:
            case_dict["parse_warnings"].append("Missing Result")
            
        return case_dict

ingest_service = IngestService()
