from typing import TypeVar, Callable, Sequence

T = TypeVar("T")
K = TypeVar("K")

def merge(list1: Sequence[T], list2: Sequence[T], key: Callable[[T], K], reverse: bool = False) -> Sequence[T]:
    """
    Merge two sorted lists into one.
    
    :param list1: First list. Assumed to be sorted
    :param list2: Second list. Assumed to be sorted.
    :param compare: Comparator that returns negative if e1 < e2, 0 if e1 == e2, and positive if e1 > e2
    :param reverse: Whether to reverse sort the list in descending order. Default False.
    :return: Merged sorted list.
    """

    len1, len2 = len(list1), len(list2)
    idx1, idx2 = 0, 0
    merged = list[T]()
    while idx1 < len1 and idx2 < len2:
        e1, e2 = list1[idx1], list2[idx2]
        cmp = (key(e1) <= key(e2)) ^ reverse # type: ignore[operator]
        if cmp: 
            merged.append(e1)
            idx1 += 1
        else:
            merged.append(e2)
            idx2 += 1
    merged.extend(list1[idx1:])
    merged.extend(list2[idx2:])
    
    return merged