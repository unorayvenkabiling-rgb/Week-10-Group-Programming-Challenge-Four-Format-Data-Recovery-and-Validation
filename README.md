# Week-10-Group-Programming-Challenge-Four-Format-Data-Recovery-and-Validation

Data Ingestion & Validation Pipeline

A robust data ingestion pipeline built to process, normalize, validate, and quarantine multi-format dataset inputs (CSV, Excel, JSON, Parquet) against a unified canonical schema.

Team & Task Ownership

Member 1: | Uno Timothy Rayven Kabiling | @unorayvenkabiling-rgb | `email@example.com` | CSV & Excel loaders, delimiter/sheet parsing, header normalization 

Member 2: | Carlos Gabriel Roman | @gabroman28 | `email@example.com` | JSON & Parquet loaders, nested record extraction, string normalization |

Member 3: | Isaiah Collado | @IsaiahCollado | isaiah.collado@ust.edu.ph | Row validation engine, quarantine logic, exact deduplication, conflicting key handling |

Member 4: | John Christian Ballesteros | @John-Christian-Ballesteros | johnchristian.ballesteros@ust.edu.ph | Pipeline integration, final dataset aggregation, peer review coordination |

Member 5: | Jeremiah Daniel Padilla | @jdpadilla2 | `email@example.com` | Pipeline integration, final dataset aggregation, peer review coordination |


Module Architecture & Workflow

1. **Loaders (`src/`)**: Format-specific modules parse raw data files (`.csv`, `.xlsx`, `.json`, `.parquet`) using `data/manifest.json` schema rules and map raw columns to canonical order.
2. **Validation & Quarantine (`src/validation.py`)**: 
   * Validates field types, non-null constraints, and value ranges for each record.
   * Isolates invalid records into a dedicated quarantine output file without stopping pipeline execution.
   * Performs exact deduplication and flags conflicting primary keys.
3. **Integration**: Aggregates all validated records across formats into a clean target dataset.

---

## 🚀 Getting Started & Execution

### Prerequisites
* Python 3.9+
* `pandas`, `pyarrow` (for Parquet handling)

### Installation
```bash
git clone <repository-url>
cd <repository-folder>
pip install -r requirements.txt
