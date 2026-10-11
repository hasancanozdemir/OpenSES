! OpenSES: closing of the JSON output file and program exit.
!
! The JSON output is a list that INPUT.FOR opens with "[" and an "info"
! object, and to which JSONPIT appends one object per print time, each
! followed by a comma.  SesExit closes the list with a "run_status"
! object and "]", so the file is valid JSON however the program ends:
! normal completion, input errors, or a simulation error part way.
!
! Every place that ends the program calls SesExit instead of EXIT.

subroutine SesExit(code)
      implicit none
      include 'DSHARE'
      integer, intent(in) :: code
      logical :: is_open
      integer :: nbytes

      inquire(unit=json, opened=is_open)
      if (is_open) then
        flush(json)
        inquire(unit=json, size=nbytes)
        ! Nothing written yet: the run stopped before INPUT opened the list.
        if (nbytes .le. 0) write(json, '(T5, "[")')

        write(json, '(T10, "{")')
        write(json, '(T10, A)') '"run_status" : {'
        write(json, '(T25, A, T60, I10, ",")') '"exit_code" :', code
        if (code .eq. 100) then
          write(json, '(T25, A, T66, A)') '"completed" :', 'true,'
        else
          write(json, '(T25, A, T65, A)') '"completed" :', 'false,'
        end if
        if (inpver .gt. 0) then
          write(json, '(T25, A, T60, F10.3, ",")') '"input_file_version" :', &
                                                   inpver / 1000.0
        end if
        write(json, '(T25, A, T50, A, A, A)') '"openses_version" :', &
                                              '"', trim(sesver), '"'
        write(json, '(T25, "}")')
        write(json, '(T10, "}")')
        write(json, '(T5, "]")')
        close(json)
      end if

      call exit(code)
end subroutine SesExit
