import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix handleWriteSubmit empty check
search_submit = """      if (!val) {
        inp.focus();
        return;
      }

      isWaitingNext = true;"""

replace_submit = """      if (!val) {
        // Hitting enter on empty input means "I don't know"
        handleWriteSkip();
        return;
      }

      isWaitingNext = true;"""
content = content.replace(search_submit, replace_submit)


# 2. Fix retype-input event listener
search_retype = """            rInp.addEventListener("input", () => {
              if (checkFuzzyMatch(rInp.value, correctVal)) {
                rInp.style.borderColor = "var(--success)";
                setTimeout(nextCardAfterFeedback, 400);
              }
            });
            rInp.addEventListener("keydown", (e) => {
              if (e.key === "Enter") nextCardAfterFeedback();
            });"""

replace_retype = """            rInp.addEventListener("input", () => {
              if (checkFuzzyMatch(rInp.value, correctVal)) {
                rInp.style.borderColor = "var(--success)";
                setTimeout(nextCardAfterFeedback, 400);
              }
            });
            rInp.addEventListener("keydown", (e) => {
              // Allow pressing enter to bypass the retype check completely
              if (e.key === "Enter") nextCardAfterFeedback();
            });"""
# Actually, the original code already allows Enter to bypass! 
# Let's change the wording in feedback so they KNOW they can bypass, or add a skip button to the feedback screen.
