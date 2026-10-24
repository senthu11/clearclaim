"""Personal details belong only to the local UI session, never agent state."""

from copy import deepcopy

import streamlit as st
from pydantic import BaseModel, ConfigDict, Field

SEX_OPTIONS = ["Not provided", "Female", "Male", "Intersex", "Prefer not to say"]


class LocalPerson(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="", max_length=120)
    age: int | None = Field(default=None, ge=0, le=120)
    sex: str = "Not provided"
    reference: str = Field(default="", max_length=100)


def personalized_bill(bill, person):
    """Local download/letter only. Never pass this copy to the graph or a model."""
    result = deepcopy(bill)
    if person.get("name"):
        result["patient"] = person["name"]
    if person.get("reference"):
        result["account"] = person["reference"]
    return result


def clear_person():
    st.session_state.pop("local_person", None)
    for key in ("person_name", "person_age", "person_sex", "person_reference"):
        st.session_state.pop(key, None)
    st.session_state["person_revision"] = st.session_state.get("person_revision", 0) + 1


def person_details():
    stored = st.session_state.get("local_person", {})
    with st.container(key="personal_details"):
        with st.expander("Personal details · optional and kept in this app session", expanded=False):
            st.caption("Stored for this session only. Name and reference can personalize your downloaded letter. "
                       "Age and sex are not used by the audit. These fields never enter the agent workflow or external requests.")
            with st.form("local_person_details"):
                name, age, sex, reference = st.columns([2, 1, 1.4, 1.6])
                name_value = name.text_input("Full name (optional)", value=stored.get("name", ""),
                                             max_chars=120, key="person_name")
                age_value = age.number_input("Age (optional)", min_value=0, max_value=120,
                                             value=stored.get("age"), step=1, key="person_age")
                sex_value = sex.selectbox("Sex (optional)", SEX_OPTIONS,
                                          index=SEX_OPTIONS.index(stored.get("sex", "Not provided")), key="person_sex")
                reference_value = reference.text_input("Bill reference (optional)", value=stored.get("reference", ""),
                                                        max_chars=100, key="person_reference")
                save, clear, note = st.columns([1, 1, 3])
                saved = save.form_submit_button("Save for this session", type="primary", width="stretch")
                clear.form_submit_button("Clear details", on_click=clear_person, width="stretch")
                note.caption(":material/lock: Local only · no internet or LLM transmission")
            if saved:
                person = LocalPerson(name=name_value.strip(), age=age_value, sex=sex_value,
                                     reference=reference_value.strip())
                st.session_state["local_person"] = person.model_dump()
                st.session_state["person_revision"] = st.session_state.get("person_revision", 0) + 1
                st.rerun()
            if stored:
                st.caption(":material/check_circle: Personal details saved for this session. You can clear them at any time.")
